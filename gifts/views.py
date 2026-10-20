from functools import wraps
import secrets
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .external import obtain_product_image
from .forms import LinkFormSet, ManagerAuthenticationForm, ProductForm, VisitorForm
from .models import Product, ProductLink, Selection


def visitor_owner(request):
    capability = request.session.get("visitor_capability")
    if not request.session.get("visitor") or not capability:
        return None
    return salted_hmac("presentes.selection.owner", capability, algorithm="sha256").hexdigest()


def products_for(owner=None):
    selected = Selection.objects.filter(product=OuterRef("pk"))
    return Product.objects.prefetch_related("links").annotate(
        is_selected=Exists(selected), is_mine=Exists(selected.filter(owner_digest=owner or "")),
    ).order_by("is_selected", "-created_at", "pk")


def manager_required(view):
    @login_required
    @wraps(view)
    def protected(request, *args, **kwargs):
        if not request.user.is_active or not request.user.has_perm("gifts.add_product"):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return protected


@require_GET
def catalog(request):
    owner = visitor_owner(request)
    identified = bool(owner)
    return render(request, "lista.html", {
        "identified": identified,
        "visitor_form": VisitorForm(),
        "products": products_for(owner) if identified else [], "allow_choices": True,
    })


@require_POST
def identify(request):
    if visitor_owner(request):
        return redirect("catalog")
    form = VisitorForm(request.POST)
    if form.is_valid():
        request.session["visitor"] = form.cleaned_data
        request.session["visitor_capability"] = secrets.token_urlsafe(32)
        request.session.set_expiry(0)
        return redirect("catalog")
    return render(request, "lista.html", {"identified": False, "visitor_form": form, "products": []}, status=400)


class ManagerLoginView(LoginView):
    template_name = "login.html"
    authentication_form = ManagerAuthenticationForm


class ManagerLogoutView(LogoutView):
    next_page = reverse_lazy("login")


def panel_context(request, form=None, links=None, submission_key=None):
    if submission_key is None:
        submission_key = str(uuid.uuid4())
        keys = request.session.get("product_submissions", [])
        request.session["product_submissions"] = (keys + [submission_key])[-8:]
    return {
        "products": products_for().select_related("selection"),
        "product_form": form or ProductForm(), "link_forms": links or LinkFormSet(prefix="links"),
        "submission_key": submission_key, "open_product_modal": form is not None,
        "can_cancel_selections": request.user.has_perm("gifts.delete_selection"),
    }


@manager_required
@require_GET
def panel(request):
    return render(request, "painel.html", panel_context(request))


@manager_required
@require_POST
def create_product(request):
    try:
        key = str(uuid.UUID(request.POST.get("submission_key", "")))
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest("Atualize o painel e tente novamente.")
    if Product.objects.filter(submission_key=key, created_by=request.user).exists():
        return redirect("panel")
    if key not in request.session.get("product_submissions", []):
        return HttpResponseBadRequest("Atualize o painel e tente novamente.")
    form = ProductForm(request.POST)
    links = LinkFormSet(request.POST, prefix="links")
    valid_form = form.is_valid()
    valid_links = links.is_valid()
    if not (valid_form and valid_links):
        return render(request, "painel.html", panel_context(request, form, links, key), status=400)
    urls = [link["url"] for link in links.cleaned_data if link.get("url")]
    image = obtain_product_image(urls, form.cleaned_data["name"])
    saved_image = None
    try:
        with transaction.atomic():
            product = Product.objects.create(name=form.cleaned_data["name"], created_by=request.user, submission_key=key)
            ProductLink.objects.bulk_create([
                ProductLink(product=product, url=url, position=position) for position, url in enumerate(urls)
            ])
            if image:
                product.image.save("product.webp", ContentFile(image), save=True)
                saved_image = product.image
    except IntegrityError:
        if saved_image:
            saved_image.delete(save=False)
        if not Product.objects.filter(submission_key=key, created_by=request.user).exists():
            raise
    else:
        if image:
            messages.success(request, "Presente cadastrado com sucesso.")
        else:
            messages.warning(request, "Presente cadastrado. Não foi possível obter a foto das lojas; usamos a imagem padrão.")
    return redirect("panel")


@require_GET
def product_image(request, pk):
    manager = request.user.is_active and request.user.has_perm("gifts.add_product")
    if not visitor_owner(request) and not manager:
        raise Http404
    product = get_object_or_404(Product, pk=pk)
    if not product.image:
        raise Http404
    try:
        return FileResponse(product.image.open("rb"), content_type="image/webp")
    except OSError:
        raise Http404 from None


@require_http_methods(["GET", "POST"])
def choose_product(request, pk):
    owner = visitor_owner(request)
    if not owner:
        return redirect("catalog")
    product = get_object_or_404(Product, pk=pk)
    if request.method == "GET":
        return render(request, "confirmar.html", {"product": product, "unavailable": Selection.objects.filter(product=product).exists()})
    identity = request.session["visitor"]
    try:
        with transaction.atomic():
            Selection.objects.create(product=product, owner_digest=owner, first_name=identity["first_name"], surname=identity["surname"])
    except IntegrityError:
        messages.warning(request, "Esse presente já foi selecionado. Você pode escolher outro item da lista.")
    else:
        messages.success(request, "Escolha confirmada! Você pode escolher mais de um presente, se quiser.")
    return redirect("catalog")


@manager_required
@permission_required("gifts.delete_selection", raise_exception=True)
@require_POST
def cancel_selection_manager(request, pk):
    selection = get_object_or_404(Selection, product_id=pk)
    selection.delete()
    messages.success(request, "Escolha cancelada. O presente está disponível novamente.")
    return redirect("panel")


@require_POST
def cancel_selection_visitor(request, pk):
    owner = visitor_owner(request)
    if not owner:
        return redirect("catalog")
    deleted, _ = Selection.objects.filter(product_id=pk, owner_digest=owner).delete()
    if not deleted:
        raise Http404
    messages.success(request, "Sua escolha foi cancelada. As suas outras escolhas foram mantidas.")
    return redirect("catalog")
