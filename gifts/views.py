from functools import wraps
import secrets
from urllib.parse import urlencode
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, F
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import IllustrationChoiceForm, LinkFormSet, ManagerAuthenticationForm, ProductForm, VisitorForm
from .models import Product, ProductLink, Selection


def visitor_owner(request):
    capability = request.session.get("visitor_capability")
    if not request.session.get("visitor") or not capability:
        return None
    return salted_hmac("presentes.selection.owner", capability, algorithm="sha256").hexdigest()


def products_for(owner=None):
    selected = Selection.objects.filter(product=OuterRef("pk"))
    return Product.objects.select_related("selection").prefetch_related("links").annotate(
        is_selected=Exists(selected), is_mine=Exists(selected.filter(owner_digest=owner or "")),
    ).order_by("is_selected", "-created_at", "pk")


def manager_required(view):
    @login_required
    @wraps(view)
    def protected(request, *args, **kwargs):
        if not request.user.is_active or not request.user.has_perm("gifts.view_product"):
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
        "can_add_products": request.user.has_perm("gifts.add_product"),
        "can_edit_products": request.user.has_perm("gifts.change_product"),
        "can_delete_products": request.user.has_perm("gifts.delete_product"),
        "can_download_database": request.user.has_perm("gifts.export_database"),
        "can_export_selections": request.user.has_perm("gifts.export_selections"),
        "panel_mode": True,
    }


@manager_required
@require_GET
def panel(request):
    return render(request, "painel.html", panel_context(request))


@manager_required
@permission_required("gifts.add_product", raise_exception=True)
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
    try:
        with transaction.atomic():
            product = Product.objects.create(
                name=form.cleaned_data["name"], illustration_choice=form.cleaned_data["illustration_choice"],
                created_by=request.user, submission_key=key,
            )
            ProductLink.objects.bulk_create([
                ProductLink(product=product, url=url, position=position) for position, url in enumerate(urls)
            ])
    except IntegrityError:
        if not Product.objects.filter(submission_key=key, created_by=request.user).exists():
            raise
    else:
        messages.success(request, "Presente cadastrado com sucesso.")
        apply_missing_illustration(request, product)
    return redirect("panel")


@require_GET
def product_image(request, pk):
    manager = request.user.is_active and request.user.has_perm("gifts.view_product")
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
            if not Product.objects.filter(pk=pk).update(revision=F("revision") + 1):
                raise Http404
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


@manager_required
@permission_required("gifts.export_database", raise_exception=True)
@require_POST
def export_database(request):
    from .exports import database_download
    import sqlite3
    try:
        return database_download()
    except (OSError, ValueError, TimeoutError, sqlite3.Error):
        return render(request, "export_error.html", status=503)


@manager_required
@permission_required("gifts.export_selections", raise_exception=True)
@require_POST
def export_selections(request):
    from .exports import selections_download
    return selections_download()


@require_GET
def health(request):
    from django.db import connection, DatabaseError
    from django.http import HttpResponse
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM django_migrations LIMIT 1")
            if not cursor.fetchone():
                raise DatabaseError
    except DatabaseError:
        return HttpResponse("unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


@manager_required
@permission_required("gifts.change_product", raise_exception=True)
@require_http_methods(["GET", "POST"])
def edit_product(request, pk):
    from .services import ProductConflict, update_product
    product = get_object_or_404(Product, pk=pk)
    if Selection.objects.filter(product=product).exists():
        messages.warning(request, "Cancele a escolha antes de editar este presente.")
        return render(request, "painel.html", panel_context(request), status=409)
    old_urls = list(product.links.values_list("url", flat=True))
    form = ProductForm(request.POST if request.method == "POST" else None, initial={"name": product.name}, include_illustration=False)
    links = LinkFormSet(request.POST if request.method == "POST" else None, initial=[{"url": url} for url in old_urls], prefix="links")
    revision = str(product.revision)
    status = 200
    if request.method == "POST":
        valid_form, valid_links = form.is_valid(), links.is_valid()
        if valid_form and valid_links:
            try:
                revision = int(request.POST.get("revision", ""))
                urls = [item["url"] for item in links.cleaned_data if item.get("url")]
                result = update_product(pk, revision, form.cleaned_data["name"], urls)
            except (ProductConflict, ValueError) as exc:
                messages.warning(request, str(exc) if isinstance(exc, ProductConflict) else "Atualize o painel e tente novamente.")
                return render(request, "painel.html", panel_context(request), status=409)
            messages.success(request, "Presente atualizado. Imagens existentes foram preservadas; use Rever ilustração para substituí-las.")
            if not result.has_available_image:
                apply_missing_illustration(request, result)
            return redirect("panel")
        status = 400
        revision = request.POST.get("revision", revision)
    context = panel_context(request, form, links)
    context.update(editing_product=product, revision=revision)
    return render(request, "painel.html", context, status=status)


@manager_required
@permission_required("gifts.delete_product", raise_exception=True)
@require_http_methods(["GET", "POST"])
def delete_product(request, pk):
    from .services import ProductConflict, delete_product as delete
    product = Product.objects.filter(pk=pk).first()
    if not product:
        return redirect("panel")
    if Selection.objects.filter(product=product).exists():
        messages.warning(request, "Cancele a escolha antes de excluir este presente.")
        return render(request, "painel.html", panel_context(request), status=409)
    if request.method == "POST":
        try:
            delete(pk, int(request.POST.get("revision", "")))
        except (ProductConflict, ValueError) as exc:
            messages.warning(request, str(exc) if isinstance(exc, ProductConflict) else "Atualize o painel e tente novamente.")
            return render(request, "painel.html", panel_context(request), status=409)
        messages.success(request, "Presente excluído.")
        return redirect("panel")
    return render(request, "painel.html", {**panel_context(request), "deleting_product": product})


def apply_missing_illustration(request, product):
    from .illustrations.service import apply_illustration
    from .services import ProductConflict
    try:
        result = apply_illustration(product.pk, product.revision)
    except (OSError, ValueError, ProductConflict):
        messages.warning(request, "Os dados foram salvos. Não foi possível aplicar a ilustração; tente pelo painel.")
        return
    if result == "no_match":
        messages.info(request, "Os dados foram salvos com a imagem padrão. Use Escolher ilustração no painel para selecionar uma imagem do catálogo.")


def illustration_selection(product, data=None):
    from .illustrations import illustration_by_key, match_illustration
    form = IllustrationChoiceForm(data, initial={"illustration_choice": product.illustration_choice}, auto_id="id_catalog_%s")
    if data is not None:
        if not form.is_valid():
            return form, None, None
        choice = form.cleaned_data["illustration_choice"]
    else:
        choice = product.illustration_choice
    candidate = illustration_by_key(choice) if choice else match_illustration(product.name)
    return form, candidate, choice


@manager_required
@permission_required("gifts.change_product", raise_exception=True)
@require_http_methods(["GET", "POST"])
def apply_product_illustration(request, pk):
    from .illustrations.service import apply_illustration
    from .services import ProductConflict
    product = get_object_or_404(Product, pk=pk)
    submitted = request.POST if request.method == "POST" else request.GET
    data = submitted if "illustration_choice" in submitted else None
    form, candidate, choice = illustration_selection(product, data)
    context = {
        **panel_context(request), "illustrating_product": product,
        "illustration_form": form, "illustration_candidate": candidate, "illustration_choice": choice or "",
        "illustration_preview_url": reverse("illustration_preview", args=[pk]) + "?" + urlencode({"illustration_choice": choice or ""}),
    }
    if form.is_bound and not form.is_valid():
        return render(request, "painel.html", context, status=400)
    if request.method == "POST":
        try:
            revision = int(request.POST.get("revision", ""))
            result = apply_illustration(
                pk, revision, replace_existing=request.POST.get("replace_image") == "1",
                illustration_choice=choice,
            )
        except ProductConflict as exc:
            messages.warning(request, str(exc))
            return render(request, "painel.html", panel_context(request), status=409)
        except (OSError, ValueError):
            messages.warning(request, "Não foi possível aplicar a ilustração. A imagem anterior foi preservada; confira o catálogo e tente novamente.")
            return render(request, "painel.html", context, status=400)
        message = {
            "applied": "Ilustração aplicada e salva. Confira o produto real nos anúncios.",
            "unchanged": "Esta ilustração já está aplicada; o arquivo foi reutilizado.",
            "preserved": "Imagem existente preservada. Abra Rever ilustração para confirmar a substituição.",
            "no_match": "Sem ilustração compatível pelo nome. Escolha uma ilustração do catálogo no painel.",
        }[result]
        messages.info(request, message)
        return redirect("panel")
    return render(request, "painel.html", context)


@manager_required
@permission_required("gifts.change_product", raise_exception=True)
@require_GET
def illustration_preview(request, pk):
    import io
    from .illustrations import read_illustration
    product = get_object_or_404(Product, pk=pk)
    data = request.GET if "illustration_choice" in request.GET else None
    _, candidate, _ = illustration_selection(product, data)
    if candidate is None:
        raise Http404
    try:
        data = read_illustration(candidate)
    except (OSError, ValueError):
        raise Http404 from None
    return FileResponse(io.BytesIO(data), content_type="image/webp")
