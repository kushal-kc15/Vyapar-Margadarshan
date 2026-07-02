from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('EXPENSE_APPROVED', 'Expense Approved'),
                    ('EXPENSE_REJECTED', 'Expense Rejected'),
                    ('EXPENSE_PENDING', 'Expense Pending Approval'),
                    ('BUDGET_ALERT', 'Budget Alert'),
                    ('BUDGET_EXCEEDED', 'Budget Exceeded'),
                    ('UNUSUAL_EXPENSE', 'Unusual Expense Submitted'),
                    ('INVITATION_RECEIVED', 'Invitation Received'),
                    ('MEMBER_JOINED', 'New Member Joined'),
                    ('ROLE_CHANGED', 'Role Changed'),
                    ('SYSTEM', 'System Notification'),
                ],
                max_length=30,
            ),
        ),
    ]
