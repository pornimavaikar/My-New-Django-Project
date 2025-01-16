from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import pytz
from django.db.models import Q
class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Supreme ID'),
        ('TL', 'Team Leader'),
        ('SRM', 'Senior Relationship Manager'),
        ('RM', 'Relationship Manager'),
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    reporting_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,related_name='reporting_users')

    # Add related_name to avoid clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    
    def get_subordinates(self):
        """Get all users reporting to this user"""
        return CustomUser.objects.filter(reporting_to=self)

    def get_team_leads(self):
        """Get all assigned leads for the user and their subordinates"""
        if self.role == 'ADMIN':
            return Lead.objects.all()
        elif self.role in ['TL', 'SRM']:
            subordinates = CustomUser.objects.filter(reporting_to=self)
            return Lead.objects.filter(assigned_to__in=subordinates)
        return Lead.objects.filter(assigned_to=self)
    
    def has_lead_access(self, lead):
    
    # Admin has access to all leads
        if self.role == 'ADMIN':
         return True
        
    # TL has access to their own leads, leads assigned to their team,
    # and leads from tasks created by/assigned to their team
        if self.role == 'TL':
         team_members = CustomUser.objects.filter(
            Q(reporting_to=self) |
            Q(reporting_to__reporting_to=self)
         )
         return (lead.assigned_to == self or
                lead.assigned_to.reporting_to == self or
                lead.task.assigned_by in team_members or
                lead.task.assigned_to in team_members)
        
    # SRM has access to their own leads, leads assigned to their RMs,
    # and leads from tasks created by/assigned to them or their RMs
        if self.role == 'SRM':
          team_members = CustomUser.objects.filter(
            Q(reporting_to=self) |
            Q(id=self.id)
         )
          return (lead.assigned_to == self or
                lead.assigned_to.reporting_to == self or
                lead.task.assigned_by == self or
                lead.task.assigned_to in team_members)
        
    # RM only has access to their own leads and leads from their tasks
        if self.role == 'RM':
            return (lead.assigned_to == self or
                lead.task.assigned_to == self)
        
        return False
    def is_admin(self):
        return self.role == 'ADMIN' or self.is_superuser

    def is_tl(self):
        return self.role == 'TL'
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    def can_view_reports(self):
        """Explicit check for report viewing permission"""
        return self.role in ['ADMIN', 'TL']
    
    def can_view_lead_list(self):
        """Explicit check for lead list viewing permission"""
        return self.role in ['ADMIN', 'TL', 'SRM']
    
    def get_team_hierarchy(self):
        """Get all users in the team hierarchy"""
        if self.role == 'TL':
            direct_reports = self.reporting_users.all()  # SRMs
            indirect_reports = CustomUser.objects.filter(
                reporting_to__in=direct_reports
            )  # RMs under SRMs
            return (direct_reports | indirect_reports).distinct()
        elif self.role == 'SRM':
            return self.reporting_users.all()  # RMs
        return CustomUser.objects.none()
class Task(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='task_files/', blank=True)
    assigned_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tasks_assigned')
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tasks_received')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Lead(models.Model):
    STATUS_CHOICES = (
        ('PROSPECT', 'Prospect'),
        ('IN', 'In'),
        ('NI', 'NI'),
        ('CNC', 'CNC'),
        ('RETAIL', 'Retail'),
        ('COMMERCIAL', 'Commercial'),
        ('VISIT_DONE', 'Visit Done'),
        ('BOOKING_DONE', 'Booking Done'),
    )
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    contact = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROSPECT')
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_contacted = models.DateTimeField(null=True, blank=True)
    next_followup_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    priority = models.CharField(max_length=10, 
                              choices=[('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')],
                              default='MEDIUM')
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL,
        null=True,
        related_name='completed_leads'
    )
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
        
    def get_formatted_changed_at(self):
        return self.changed_at.strftime('%d-%m-%Y %I:%M %p')
    class Meta:
        ordering = ['-created_at']
    class Meta:
        indexes = [
            models.Index(fields=['assigned_to']),
            models.Index(fields=['task']),
            models.Index(fields=['status']),
        ]# Order by most recent by default
class Attendance(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='Present')
    
    def __str__(self):
        return f"{self.user.username} - {self.date}"
    
    def get_check_in_local(self):
        if self.check_in:
            return timezone.localtime(self.check_in, pytz.timezone('Asia/Kolkata'))
        return None
    
    def get_check_out_local(self):
        if self.check_out:
            return timezone.localtime(self.check_out, pytz.timezone('Asia/Kolkata'))
        return None
    def get_formatted_check_in(self):
        local_time = self.get_check_in_local()
        if local_time:
            return local_time.strftime("%I:%M %p")
        return None

    def get_formatted_check_out(self):
        local_time = self.get_check_out_local()
        if local_time:
            return local_time.strftime("%I:%M %p")
        return None
    
class LeadFollowup(models.Model):
    """New model to track lead followups"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='followups')
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    notes = models.TextField()
    followup_date = models.DateField()
    outcome = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
    
class LeadStatusHistory(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, choices=Lead.STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=Lead.STATUS_CHOICES)
    changed_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    changed_at = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-changed_at'] 
        
    def get_formatted_changed_at(self):
        local_tz = pytz.timezone('Asia/Kolkata')
        return timezone.localtime(self.changed_at, local_tz).strftime("%d-%m-%Y %I:%M %p")
    
class Notification(models.Model):
    """Model to store notifications for senior team members"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']

    def mark_as_read(self):
        self.read = True
        self.save()
        
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
