from django.urls import path
from . import views

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("identificar/", views.identify, name="identify"),
    path("login/", views.ManagerLoginView.as_view(), name="login"),
    path("sair/", views.ManagerLogoutView.as_view(), name="logout"),
    path("painel/", views.panel, name="panel"),
    path("painel/adicionar/", views.create_product, name="create_product"),
    path("painel/<uuid:pk>/editar/", views.edit_product, name="edit_product"),
    path("painel/<uuid:pk>/excluir/", views.delete_product, name="delete_product"),
    path("painel/<uuid:pk>/ilustracao/", views.apply_product_illustration, name="apply_illustration"),
    path("painel/<uuid:pk>/ilustracao/preview/", views.illustration_preview, name="illustration_preview"),
    path("painel/<uuid:pk>/foto/", views.apply_product_illustration, name="retry_product_image"),
    path("painel/exportar/banco/", views.export_database, name="export_database"),
    path("painel/exportar/conferencia/", views.export_selections, name="export_selections"),
    path("healthz/", views.health, name="health"),
    path("imagens/<uuid:pk>/", views.product_image, name="product_image"),
    path("escolher/<uuid:pk>/", views.choose_product, name="choose_product"),
    path("escolhas/<uuid:pk>/cancelar/", views.cancel_selection_visitor, name="cancel_selection_visitor"),
    path("painel/escolhas/<uuid:pk>/cancelar/", views.cancel_selection_manager, name="cancel_selection_manager"),
]
