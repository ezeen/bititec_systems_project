# Generated migration for adding QR code fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bititec', '0043_storeaccessoryinquiry_lease_storepartinquiry_lease'),
    ]

    operations = [
        migrations.AddField(
            model_name='machine',
            name='qr_code',
            field=models.ImageField(blank=True, null=True, upload_to='qr_codes/machines/'),
        ),
        migrations.AddField(
            model_name='machine',
            name='auto_generated_serial',
            field=models.BooleanField(default=False, help_text='Whether serial number was auto-generated'),
        ),
        migrations.AddField(
            model_name='part',
            name='qr_code',
            field=models.ImageField(blank=True, null=True, upload_to='qr_codes/parts/'),
        ),
        migrations.AddField(
            model_name='part',
            name='auto_generated_ref',
            field=models.BooleanField(default=False, help_text='Whether reference number was auto-generated'),
        ),
        migrations.AddField(
            model_name='accessory',
            name='qr_code',
            field=models.ImageField(blank=True, null=True, upload_to='qr_codes/accessories/'),
        ),
        migrations.AddField(
            model_name='accessory',
            name='auto_generated_ref',
            field=models.BooleanField(default=False, help_text='Whether reference number was auto-generated'),
        ),
    ]
