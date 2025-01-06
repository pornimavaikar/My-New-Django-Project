from django import forms
from .models import Task, Lead, Attendance, CustomUser,LeadFollowup
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.db.models import Q
from django.core.exceptions import ValidationError
import pandas as pd

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'file', 'assigned_to']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            print(f"\nTaskForm Init:")
            print(f"Current user: {user.username}")
            print(f"User role: {user.role}")
            
            # Initialize an empty queryset
            assignable_users = CustomUser.objects.none()
            
            if user.role == 'TL':
                # Get all SRMs who report to this TL
                assignable_users = CustomUser.objects.filter(
                    role='SRM',
                    is_active=True
                ).filter(
                    Q(reporting_to=user) | 
                    Q(reporting_to__isnull=True)  # Include unassigned SRMs
                )
                print(f"Found {assignable_users.count()} assignable SRMs")
            
            elif user.role == 'SRM':
                # Get all RMs who report to this SRM
                assignable_users = CustomUser.objects.filter(
                    role='RM',
                    is_active=True
                ).filter(
                    Q(reporting_to=user) |
                    Q(reporting_to__isnull=True)  # Include unassigned RMs
                )
                print(f"Found {assignable_users.count()} assignable RMs")
            
            elif user.role == 'ADMIN':
                # Admin can assign to any TL or SRM
                assignable_users = CustomUser.objects.filter(
                    role__in=['TL', 'SRM'],
                    is_active=True
                )
                print(f"Found {assignable_users.count()} assignable users for Admin")
            
            # Debug output
            for u in assignable_users:
                print(f"- {u.username} (Role: {u.role}, Reports to: {u.reporting_to.username if u.reporting_to else 'None'})")
            
            self.fields['assigned_to'].queryset = assignable_users
            
            # Add help text
            self.fields['assigned_to'].help_text = "Select a user to assign this task to"
            self.fields['file'].validators.append(self.validate_excel_file)
        self.fields['file'].help_text = "Upload Excel file (.xlsx, .xls) containing leads data"

    def validate_excel_file(self, value):
        if value:
            ext = value.name.split('.')[-1].lower()
            if ext not in ['xlsx', 'xls']:
                raise forms.ValidationError('Only Excel files (.xlsx, .xls) are allowed')
            
            # Validate file size (5MB limit)
            if value.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 5MB')

            try:
                df = pd.read_excel(value)
                required_columns = ['name', 'contact']
                missing_columns = [col for col in required_columns if col.lower() not in [c.lower() for c in df.columns]]
                
                if missing_columns:
                    raise forms.ValidationError(f'Missing required columns: {", ".join(missing_columns)}')
                
            except Exception as e:
                raise forms.ValidationError(f'Error processing Excel file: {str(e)}')
        return value

            

class LeadStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['status']
        
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role', 'reporting_to')

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role', 'reporting_to')

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_role'})
    )
    reporting_to = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        empty_label="Select Reporting Manager",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_reporting_to'})
    )
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role', 'reporting_to', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to password fields
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'
        
        # Initialize reporting_to queryset
        role = self.data.get('role')
        if role:
            self.fields['reporting_to'].queryset = self.get_reporting_to_queryset(role)
        
        # Add help texts
        self.fields['username'].help_text = 'Required. 150 characters or fewer.'
        self.fields['email'].help_text = 'Required. Enter a valid email address.'
        self.fields['role'].help_text = 'Select your role in the organization.'
        self.fields['reporting_to'].help_text = 'Select your reporting manager.'

    def get_reporting_to_queryset(self, role):
        if role == 'RM':
            return CustomUser.objects.filter(role='SRM')
        elif role == 'SRM':
            return CustomUser.objects.filter(role='TL')
        elif role == 'TL':
            return CustomUser.objects.filter(role='ADMIN')
        return CustomUser.objects.none()
class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['status', 'remarks', 'priority', 'next_followup_date']

class LeadFollowupForm(forms.ModelForm):
    class Meta:
        model = LeadFollowup
        fields = ['notes', 'followup_date', 'outcome']