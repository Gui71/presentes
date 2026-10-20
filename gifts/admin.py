from django.contrib import admin
from .models import Product, ProductLink, Selection


class LinkInline(admin.TabularInline):
    model = ProductLink
    fields = ("position", "url")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    search_fields = ("name",)
    fields = ("name", "created_by", "created_at", "image")
    readonly_fields = fields
    inlines = [LinkInline]

    def has_add_permission(self, request):
        return False


admin.site.site_header = "Casa nova · Administração"
admin.site.site_title = "Casa nova"
admin.site.index_title = "Administração geral e acessos"


@admin.register(Selection)
class SelectionAdmin(admin.ModelAdmin):
    list_display = ("product", "first_name", "surname", "created_at")
    fields = ("product", "first_name", "surname", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False
