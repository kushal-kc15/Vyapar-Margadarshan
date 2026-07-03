from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Notification


User = get_user_model()


class ClearAllNotificationsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='notifications-user',
            email='notifications@example.com',
            password='test-password',
        )
        self.other_user = User.objects.create_user(
            username='other-notifications-user',
            email='other-notifications@example.com',
            password='test-password',
        )
        Notification.objects.create(
            user=self.user,
            notification_type='SYSTEM',
            title='Unread notification',
            message='Unread message',
        )
        Notification.objects.create(
            user=self.user,
            notification_type='SYSTEM',
            title='Read notification',
            message='Read message',
            is_read=True,
        )
        self.other_notification = Notification.objects.create(
            user=self.other_user,
            notification_type='SYSTEM',
            title='Other user notification',
            message='Other user message',
        )
        self.client.force_authenticate(self.user)

    def test_clear_all_deletes_read_and_unread_notifications_for_current_user(self):
        response = self.client.delete('/api/notifications/clear_all/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertFalse(Notification.objects.filter(user=self.user).exists())
        self.assertTrue(Notification.objects.filter(pk=self.other_notification.pk).exists())
