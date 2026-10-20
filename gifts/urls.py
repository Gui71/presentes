from django.urls import path
from . import views

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("identificar/", views.identify, name="identify"),
    path("login/", views.ManagerLoginView.as_view(), name="login"),
    path("sair/", views.ManagerLogoutView.as_view(), name="logout"),
    path("painel/", views.panel, name="panel"),
    path("painel/adicionar/", views.create_product, name="create_product"),
    path("imagens/<uuid:pk>/", views.product_image, name="product_image"),
    path("escolher/<uuid:pk>/", views.choose_product, name="choose_product"),
    path("escolhas/<uuid:pk>/cancelar/", views.cancel_selection_visitor, name="cancel_selection_visitor"),
    path("painel/escolhas/<uuid:pk>/cancelar/", views.cancel_selection_manager, name="cancel_selection_manager"),
]
