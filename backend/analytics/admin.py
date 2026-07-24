from django.contrib import admin

from .models import BusinessRule


@admin.register(BusinessRule)
class BusinessRuleAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'score', 'severity', 'enabled', 'version', 'updated_at']
    list_filter = ['category', 'severity', 'enabled']
    search_fields = ['code', 'name', 'description']
    list_editable = ['enabled', 'score', 'severity']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        (None, {'fields': ['code', 'name', 'category', 'description']}),
        ('Scoring', {'fields': ['score', 'severity', 'threshold']}),
        ('Configuration', {'fields': ['recommendation', 'enabled', 'version']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]
