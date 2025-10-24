# management/commands/generate_lease_service_calls.py
import os
import sys
import django
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
import logging

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bit_app.settings')
django.setup()

from ..models import LeaseServiceSchedule, Call
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate scheduled service calls for active lease service schedules'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Display detailed output',
        )
    
    def handle(self, *args, **options):
        verbose = options['verbose']
        today = date.today()
        
        self.stdout.write(f"Starting service call generation for {today}...")
        
        # Get active schedules that haven't expired
        active_schedules = LeaseServiceSchedule.objects.filter(
            is_active=True,
            end_date__gte=today
        ).select_related(
            'lease', 
            'lease__client', 
            'lease__item'
        ).prefetch_related('default_technicians')
        
        if verbose:
            self.stdout.write(f"Found {active_schedules.count()} active schedules")
        
        total_generated = 0
        
        for schedule in active_schedules:
            try:
                if verbose:
                    self.stdout.write(f"Processing schedule {schedule.id} for lease {schedule.lease.lease_no}")
                
                generated_calls = schedule.generate_next_service_calls()
                total_generated += len(generated_calls)
                
                if generated_calls and verbose:
                    self.stdout.write(
                        f"  Generated {len(generated_calls)} calls for schedule {schedule.id}"
                    )
                    
            except Exception as e:
                error_msg = f"Error generating calls for schedule {schedule.id}: {str(e)}"
                logger.error(error_msg)
                self.stderr.write(error_msg)
        
        if total_generated > 0:
            success_msg = f'Successfully generated {total_generated} service calls from {active_schedules.count()} schedules'
            self.stdout.write(self.style.SUCCESS(success_msg))
            logger.info(success_msg)
        else:
            self.stdout.write("No service calls generated today")
