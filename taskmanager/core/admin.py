from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Task, Lead, Attendance, LeadStatusHistory
from .forms import CustomUserCreationForm, CustomUserChangeForm

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active',)
    list_filter = ('role', 'is_staff', 'is_active',)
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'role', 'reporting_to')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'password1', 'password2',
                'role', 'reporting_to', 'is_staff', 'is_active'
            )}
        ),
    )
    search_fields = ('username', 'email',)
    ordering = ('username',)

class LeadInline(admin.TabularInline):
    model = Lead
    extra = 0

class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assigned_by', 'assigned_to', 'created_at')
    list_filter = ('assigned_by', 'assigned_to')
    inlines = [LeadInline]

class LeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact', 'status', 'assigned_to', 'updated_at')
    list_filter = ('status', 'assigned_to')
    search_fields = ('name', 'contact')

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Task, TaskAdmin)
admin.site.register(Lead, LeadAdmin)
admin.site.register(Attendance)