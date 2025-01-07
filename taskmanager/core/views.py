from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView,DetailView
from .models import Task, Lead, Attendance
from .forms import TaskForm, LeadStatusUpdateForm
import pandas as pd
from django.utils import timezone
from django.db.models import Count, Q
from .permissions import role_required, RoleRequiredMixin
from django.views import View
import openpyxl
from django.http import HttpResponse,JsonResponse
from django.shortcuts import get_object_or_404
from .models import Lead,LeadStatusHistory
from .permissions import get_leads_for_user
from .forms import RegistrationForm,LeadFollowupForm
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib import messages
from .models import CustomUser
from django.contrib.auth.views import LogoutView
import pytz
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator,EmptyPage,PageNotAnInteger
from django.views.decorators.csrf import csrf_exempt
from .models import Notification
from django.db.models.signals import post_save
from django.dispatch import receiver

class RegistrationView(CreateView):
    template_name = 'core/register.html'
    form_class = RegistrationForm
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, 'Registration successful! Please login.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Registration failed. Please correct the errors.')
        return super().form_invalid(form)
    
@login_required
def dashboard(request):
    user = request.user
    local_tz = pytz.timezone('Asia/Kolkata')
    current_time_local = timezone.localtime(timezone.now(), local_tz)
    today_date = current_time_local.date()
    
    # Get today's attendance for the current user
    attendance = Attendance.objects.filter(
        user=request.user,
        date=today_date
    ).first()

    # Function to get subordinates based on role
    def get_subordinates(user):
        subordinates = CustomUser.objects.none()
        if user.role == 'ADMIN':
            # Admin can see all users except other admins
            subordinates = CustomUser.objects.exclude(role='ADMIN')
        elif user.role == 'TL':
            # TL can see SRMs and RMs under them
            subordinates = CustomUser.objects.filter(
                Q(role__in=['SRM', 'RM']) &
                (Q(reporting_to=user) | Q(reporting_to__reporting_to=user))
            )
        elif user.role == 'SRM':
            # SRM can see only RMs under them
            subordinates = CustomUser.objects.filter(
                role='RM',
                reporting_to=user
            )
        return subordinates

    # Get subordinates' attendance
    subordinates = get_subordinates(user)
    team_attendance = Attendance.objects.filter(
        date=today_date,
        user__in=subordinates
    ).select_related('user')
    
    # Convert times to local timezone
    for att in team_attendance:
        att.check_in = timezone.localtime(att.check_in, local_tz)
        if att.check_out:
            att.check_out = timezone.localtime(att.check_out, local_tz)

    # Get reporting manager's attendance (if any)
    reporting_manager_attendance = None
    if user.role != 'ADMIN' and user.reporting_to:
        reporting_manager_attendance = Attendance.objects.filter(
            date=today_date,
            user=user.reporting_to
        ).select_related('user').first()
        
        if reporting_manager_attendance:
            reporting_manager_attendance.check_in = timezone.localtime(
                reporting_manager_attendance.check_in, local_tz)
            if reporting_manager_attendance.check_out:
                reporting_manager_attendance.check_out = timezone.localtime(
                    reporting_manager_attendance.check_out, local_tz)

    context = {
        'leads': get_leads_for_user(request.user),
        'status_choices': Lead.STATUS_CHOICES,
        'today_attendance': attendance,
        'assigned_tasks': Task.objects.filter(assigned_to=request.user).order_by('-created_at')[:5],
        'team_attendance': team_attendance,
        'reporting_manager_attendance': reporting_manager_attendance,
        'is_senior': user.role in ['ADMIN', 'TL', 'SRM'],
        'user_role': user.role
    }
    return render(request, 'core/dashboard.html', context)
class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'core/task_create.html'
    success_url = reverse_lazy('task_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        print(f"Passing user to form: {self.request.user.username} (Role: {self.request.user.role})")
        return kwargs

    def form_valid(self, form):
        form.instance.assigned_by = self.request.user
        response = super().form_valid(form)
        task = self.object
        
        if task.file:
            try:
                df = pd.read_excel(task.file)
                
                # Print column names for debugging
                print("Found columns in Excel:", df.columns.tolist())
                
                # Try different possible column name variations
                name_columns = ['name', 'Name', 'NAME', 'Customer Name', 'CustomerName', 'customer_name']
                contact_columns = ['contact', 'Contact', 'CONTACT', 'Phone', 'Mobile', 'phone_number', 'mobile_number']
                
                # Find the actual column names
                name_col = None
                contact_col = None
                
                for col in df.columns:
                    if col.lower().strip() in [n.lower() for n in name_columns]:
                        name_col = col
                    elif col.lower().strip() in [c.lower() for c in contact_columns]:
                        contact_col = col
                
                if not name_col or not contact_col:
                    messages.error(
                        self.request,
                        f'Required columns not found. Please ensure your Excel file has columns for name ({", ".join(name_columns)}) and contact ({", ".join(contact_columns)})'
                    )
                    return response
                
                leads_created = 0
                errors = []
                
                # Process each row
                for index, row in df.iterrows():
                    try:
                        # Skip empty rows
                        if pd.isna(row[name_col]) or pd.isna(row[contact_col]):
                            continue
                            
                        lead = Lead.objects.create(
                            task=task,
                            name=str(row[name_col]).strip(),
                            contact=str(row[contact_col]).strip(),
                            status='PROSPECT',
                            assigned_to=task.assigned_to
                        )
                        leads_created += 1
                        
                        LeadStatusHistory.objects.create(
                            lead=lead,
                            old_status='PROSPECT',
                            new_status='PROSPECT',
                            changed_by=self.request.user
                        )
                        
                    except Exception as e:
                        errors.append(f"Row {index + 2}: {str(e)}")
                
                if leads_created > 0:
                    messages.success(
                        self.request,
                        f'Task created successfully! {leads_created} leads imported.'
                    )
                else:
                    messages.warning(
                        self.request,
                        'No leads were imported. Please check your Excel file format.'
                    )
                
                if errors:
                    messages.warning(
                        self.request,
                        f'Some rows could not be imported. Please check the following rows: {", ".join(errors)}'
                    )
                    
            except Exception as e:
                messages.error(
                    self.request,
                    f'Error processing Excel file: {str(e)}'
                )
        return response
    def form_invalid(self, form):
        messages.error(self.request, 'Error creating task. Please check the form.')
        return super().form_invalid(form)



@login_required
def mark_attendance(request):
    local_tz = pytz.timezone('Asia/Kolkata')
    current_time_utc = timezone.now()
    current_time_local = timezone.localtime(current_time_utc, local_tz)
    today_date = current_time_local.date()
    
    if request.method == 'POST':
        existing_attendance = Attendance.objects.filter(
            user=request.user,
            date=today_date
        ).first()
        
        if not existing_attendance:
            attendance = Attendance.objects.create(
                user=request.user,
                date=today_date,
                check_in=current_time_utc,
                status='Present'
            )
            messages.success(request, f'Check-in marked successfully at {attendance.get_formatted_check_in()}!')
            
        elif not existing_attendance.check_out:
            existing_attendance.check_out = current_time_utc
            existing_attendance.save()
            messages.success(request, f'Check-out marked successfully at {existing_attendance.get_formatted_check_out()}!')
        else:
            messages.warning(request, 'Already checked out for today')
    
    return redirect('dashboard')

class ReportView(LoginRequiredMixin, RoleRequiredMixin, View):
    roles_required = ['ADMIN', 'TL', 'SRM']
    template_name = 'core/reports.html'

    def get(self, request):
        leads = get_leads_for_user(request.user)
        context = {
            'status_summary': leads.values('status').annotate(count=Count('id')),
            'daily_updates': leads.filter(
                updated_at__date=timezone.now().date()
            ).order_by('-updated_at'),
            'team_performance': leads.values(
                'assigned_to__username'
            ).annotate(
                total_leads=Count('id'),
                converted=Count('id', filter=Q(status='BOOKING_DONE'))
            )
        }
        return render(request, self.template_name, context)

@login_required
@role_required('ADMIN', 'TL', 'SRM')
def export_report(request):
    try:
        leads = get_leads_for_user(request.user)
        
        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="leads_report.xlsx"'
        
        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Leads Report"
        
        # Add headers
        headers = ['Name', 'Contact', 'Status', 'Assigned To', 'Last Updated']
        ws.append(headers)
        
        # Add data
        for lead in leads:
            ws.append([
                lead.name,
                lead.contact,
                lead.get_status_display(),
                lead.assigned_to.username,
                lead.updated_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        # Save workbook
        wb.save(response)
        
        # Make sure the file pointer is at the beginning
        if hasattr(response, 'seek'):
            response.seek(0)
        
        return response
        
    except Exception as e:
        print(f"Error generating Excel report: {str(e)}")  # For debugging
        messages.error(request, "Error generating Excel report. Please try again.")
        return redirect('reports')
# views.py
@login_required
def lead_dashboard(request):
    user = request.user
    leads = user.get_team_leads()
    
    # Get status counts
    status_counts = leads.values('status').annotate(count=Count('id'))
    
    # Get leads requiring followup today
    today = timezone.now().date()
    followup_leads = leads.filter(
        next_followup_date=today,
        status__in=['PROSPECT', 'IN', 'VISIT_DONE']
    )
    
    # Recent status changes
    recent_changes = LeadStatusHistory.objects.filter(
        lead__in=leads
    ).select_related('lead', 'changed_by')[:10]
    
    context = {
        'status_counts': status_counts,
        'followup_leads': followup_leads,
        'recent_changes': recent_changes,
        'status_choices': Lead.STATUS_CHOICES
    }
    return render(request, 'leads/dashboard.html', context)

@login_required
def lead_list(request):
    leads = get_leads_for_user(request.user)
    context = {
        'leads': leads,
        'status_choices': Lead.STATUS_CHOICES,
    }
    return render(request, 'core/lead_list.html', context)

@login_required
def lead_detail(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    followups = lead.followups.select_related('created_by').order_by('-created_at')
    status_history = lead.status_history.select_related('changed_by').order_by('-changed_at')
    
    if request.method == 'POST':
        form = LeadFollowupForm(request.POST)
        if form.is_valid():
            followup = form.save(commit=False)
            followup.lead = lead
            followup.created_by = request.user
            followup.save()
            
            # Update lead's next followup date
            lead.next_followup_date = followup.followup_date
            lead.last_contacted = timezone.now()
            lead.save()
            
            return redirect('lead_detail', pk=pk)
    else:
        form = LeadFollowupForm()
    
    context = {
        'lead': lead,
        'followups': followups,
        'status_history': status_history,
        'form': form
    }
    return render(request, 'core/lead_detail.html', context)

@login_required
def lead_management(request):
    leads = get_leads_for_user(request.user)
    paginator = Paginator(leads, 25)  # Show 25 leads per page
    
    page = request.GET.get('page')
    try:
        leads = paginator.page(page)
    except PageNotAnInteger:
        leads = paginator.page(1)
    except EmptyPage:
        leads = paginator.page(paginator.num_pages)
    
    context = {
        'leads': leads,
        'status_choices': Lead.STATUS_CHOICES,
    }
    return render(request, 'core/lead_management.html', context)

@csrf_exempt
@login_required
def update_lead_status(request, lead_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body.decode('utf-8'))
        lead = Lead.objects.select_related('assigned_to').get(id=lead_id)
        
        if not request.user.has_lead_access(lead):
            return JsonResponse({'error': 'Permission denied'}, status=403)
            
        old_status = lead.status
        new_status = data.get('status')
        
        # Update the lead
        lead.status = new_status
        lead.save()
        
        # Create history entry
        history_entry = LeadStatusHistory.objects.create(
            lead=lead,
            old_status=old_status,
            new_status=new_status,
            changed_by=request.user,
            remarks=data.get('notes', '')
        )
        
        # Create notifications for seniors
        if request.user.reporting_to:
            seniors = CustomUser.objects.filter(
                Q(id=request.user.reporting_to.id) |
                Q(role__in=['TL', 'ADMIN'])
            ).distinct()
            
            for senior in seniors:
                Notification.objects.create(
                    user=senior,
                    title=f'Lead Status Update: {lead.name}',
                    message=(
                        f'Status changed from {lead.get_status_display()} to '
                        f'{dict(Lead.STATUS_CHOICES)[new_status]} by '
                        f'{request.user.get_full_name() or request.user.username}'
                    ),
                    lead=lead
                )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Lead status updated successfully',
            'lead_id': lead.id,
            'updated_at': timezone.localtime(lead.updated_at).strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required
def get_lead_history(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
        history = lead.status_history.select_related('changed_by').order_by('-changed_at')
        
        # Create a dict of status choices for lookup
        status_choices = dict(Lead.STATUS_CHOICES)
        
        data = [{
            'changed_by': entry.changed_by.get_full_name() or entry.changed_by.username,
            'old_status': status_choices.get(entry.old_status, entry.old_status),
            'new_status': status_choices.get(entry.new_status, entry.new_status),
            'changed_at': timezone.localtime(entry.changed_at).strftime('%Y-%m-%d %I:%M %p'),
            'remarks': entry.remarks
        } for entry in history]
        
        return JsonResponse({'history': data})
    except Lead.DoesNotExist:
        return JsonResponse({'error': 'Lead not found'}, status=404)
def lead_management_view(request):
    leads = Lead.objects.all().order_by('-created_at')  # Ensure consistent ordering
    paginator = Paginator(leads, 25)  # Show 25 leads per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'lead_management.html', {'page_obj': page_obj})
 # views.py
@login_required
def lead_list_by_status(request, status=None):
    leads = get_leads_for_user(request.user)
    
    if status:
        leads = leads.filter(status=status)
    
    context = {
        'leads': leads,
        'status_choices': Lead.STATUS_CHOICES,
        'current_status': status
    }
    return render(request, 'core/lead_list.html', context)
      


@login_required
def get_leads(request):
    leads = get_leads_for_user(request.user)
    leads_data = [{
        'id': lead.id,
        'name': lead.name,
        'contact': lead.contact,
        'status': lead.status,
        'updated_at': lead.updated_at.isoformat()
    } for lead in leads]
    return JsonResponse({'leads': leads_data})

def get_reporting_to_options(request):
    role = request.GET.get('role')
    print(f"Requested role: {role}")
    
    # Query users based on role hierarchy
    if role == 'RM':
        users = CustomUser.objects.filter(role='SRM', is_active=True)
    elif role == 'SRM':
        users = CustomUser.objects.filter(role='TL', is_active=True)
    elif role == 'TL':
        users = CustomUser.objects.filter(role='ADMIN', is_active=True)
    else:
        users = CustomUser.objects.none()
    
    # Print each user found for debugging
    for user in users:
        print(f"Found user: {user.username} (Role: {user.role})")
    
    options = []
    for user in users:
        name = user.get_full_name() if user.get_full_name() else user.username
        options.append({
            'id': user.id,
            'name': f"{name} ({user.get_role_display()})"
        })
    
    print(f"Returning options: {options}")
    
    return JsonResponse({
        'options': options,
        'debug_info': {
            'requested_role': role,
            'users_found': users.count(),
            'options_created': len(options)
        }
    })
    # Debug print
    print(f"Returning options: {options}")
    
    return JsonResponse({'options': options})
class TaskListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = 'core/task_list.html'
    context_object_name = 'tasks'
    
    def get_queryset(self):
        user = self.request.user
        
        # Base queryset
        queryset = Task.objects.all()
        
        if user.role == 'ADMIN':
            return queryset.order_by('-created_at')
            
        elif user.role == 'TL':
            subordinates = CustomUser.objects.filter(reporting_to=user)
            return queryset.filter(
                Q(assigned_by=user) |
                Q(assigned_to=user) |
                Q(assigned_to__in=subordinates)
            ).order_by('-created_at')
            
        elif user.role == 'SRM':
            subordinates = CustomUser.objects.filter(reporting_to=user)
            return queryset.filter(
                Q(assigned_by=user) |
                Q(assigned_to=user) |
                Q(assigned_to__in=subordinates)
            ).order_by('-created_at')
            
        elif user.role == 'RM':
            # RMs see tasks assigned to them
            return queryset.filter(assigned_to=user).order_by('-created_at')
            
        return Task.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # All users see their assigned tasks
        context['assigned_tasks'] = Task.objects.filter(
            assigned_to=user
        ).order_by('-created_at')
        
        # TL/SRM/ADMIN see tasks they created
        if user.role in ['TL', 'SRM', 'ADMIN']:
            context['created_tasks'] = Task.objects.filter(
                assigned_by=user
            ).order_by('-created_at')
        
        # TL/SRM see tasks assigned to their team
        if user.role in ['TL', 'SRM']:
            subordinates = CustomUser.objects.filter(reporting_to=user)
            context['team_tasks'] = Task.objects.filter(
                assigned_to__in=subordinates
            ).order_by('-created_at')
        
        return context
    def get_queryset(self):
        return Task.objects.filter(assigned_to=self.request.user)

class TaskDetailView(LoginRequiredMixin, DetailView):
    model = Task
    template_name = 'core/task_detail.html'
    context_object_name = 'task'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        context['can_edit'] = self.request.user == task.assigned_by or self.request.user == task.assigned_to
        return context

    def get_queryset(self):
        # Users can only view tasks they created or are assigned to
        return Task.objects.filter(
            Q(assigned_by=self.request.user) | 
            Q(assigned_to=self.request.user)
        
        )
class CustomLogoutView(LogoutView):
    next_page = 'login'
    template_name = 'core/login.html'
    

@receiver(post_save, sender=LeadStatusHistory)
def notify_seniors_of_status_change(sender, instance, created, **kwargs):
    """
    Signal handler to notify senior team members when a lead status changes
    """
    if not created:
        return

    lead = instance.lead
    changed_by = instance.changed_by
    
    # Get all seniors in the hierarchy
    seniors = CustomUser.objects.filter(
        Q(id=changed_by.reporting_to_id) |  # Immediate supervisor
        Q(id__in=CustomUser.objects.filter(  # Higher level supervisors
            role__in=['TL', 'ADMIN'],
            reporting_users__in=[changed_by.reporting_to_id]
        ))
    ).distinct()

    # Create notification entry for each senior
    for senior in seniors:
        Notification.objects.create(
            user=senior,
            title=f'Lead Status Update: {lead.name}',
            message=(
                f'Status changed from {instance.old_status} to {instance.new_status} '
                f'by {changed_by.get_full_name() or changed_by.username}'
            ),
            lead=lead,
            created_at=timezone.now()
        )

# Add to views.py
@login_required
def notifications(request):
    """View to display notifications for the current user"""
    notifications = Notification.objects.filter(
        user=request.user,
        read=False
    ).select_related('lead')
    
    return JsonResponse({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'lead_id': n.lead_id,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'read': n.read
        } for n in notifications]
    })

@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    return JsonResponse({'status': 'success'})# In views.py

@login_required
def get_lead_work_details(request, lead_id):
    try:
        lead = Lead.objects.select_related('assigned_to').get(id=lead_id)
        
        # Check if user has permission to view work details
        if not (request.user.role in ['ADMIN', 'TL'] or request.user == lead.assigned_to.reporting_to):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Get all communications/followups for this lead
        communications = lead.followups.all().order_by('-created_at')
        
        # Calculate metrics
        total_interactions = communications.count()
        last_contacted = lead.last_contacted.strftime('%Y-%m-%d %H:%M') if lead.last_contacted else 'Never'
        next_followup = lead.next_followup_date.strftime('%Y-%m-%d') if lead.next_followup_date else 'Not scheduled'
        
        # Calculate days in current status
        days_in_status = (timezone.now().date() - lead.status_history.latest('changed_at').changed_at.date()).days
        
        response_data = {
            'rm_name': lead.assigned_to.get_full_name() or lead.assigned_to.username,
            'status': lead.get_status_display(),
            'days_in_status': days_in_status,
            'total_interactions': total_interactions,
            'last_contacted': last_contacted,
            'next_followup': next_followup,
            'communications': [{
                'date': comm.created_at.strftime('%Y-%m-%d %H:%M'),
                'notes': comm.notes
            } for comm in communications],
            'metrics': {
                'avg_response_time': calculate_avg_response_time(communications),
                'followup_rate': calculate_followup_rate(communications),
                'conversion_rate': calculate_conversion_rate(lead)
            }
        }
        
        return JsonResponse(response_data)
        
    except Lead.DoesNotExist:
        return JsonResponse({'error': 'Lead not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Helper functions for metrics calculation
def calculate_avg_response_time(communications):
    if not communications:
        return 0
    # Calculate average time between followups
    response_times = []
    prev_time = None
    for comm in communications:
        if prev_time:
            diff = (comm.created_at - prev_time).total_seconds() / 3600  # Convert to hours
            response_times.append(diff)
        prev_time = comm.created_at
    return round(sum(response_times) / len(response_times)) if response_times else 0

def calculate_followup_rate(communications):
    if not communications:
        return 0
    # Calculate percentage of followups done within 24 hours of scheduled time
    on_time_followups = len([c for c in communications if c.is_on_time()])
    return round((on_time_followups / len(communications)) * 100)

def calculate_conversion_rate(lead):
    # Calculate conversion rate based on status progression
    history = lead.status_history.all()
    if not history:
        return 0
    progressed_statuses = len(set(h.new_status for h in history))
    total_possible_statuses = len(Lead.STATUS_CHOICES)
    return round((progressed_statuses / total_possible_statuses) * 100)