import io
import shutil
import tempfile
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from kombu.exceptions import OperationalError
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from organizations.models import Organization, OrganizationMember
from expenses.models import Expense
from receipts.models import Receipt
from notifications.models import Notification
from receipts.services.ai_receipt_extractor import (
    AIReceiptExtractionError,
    GeminiReceiptExtractor,
)

User = get_user_model()

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ReceiptExpenseDateTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="receiptdateowner",
            email="receipt-date@example.com",
            password="StrongPass123!",
            email_verified=True,
        )
        self.organization = Organization.objects.create(name="Receipt Date Org")
        OrganizationMember.objects.create(
            user=self.user,
            organization=self.organization,
            role="OWNER",
        )
        self.user.active_organization = self.organization
        self.user.save(update_fields=["active_organization"])
        self.client.force_authenticate(self.user)

    def create_verified_receipt(self, receipt_date):
        return Receipt.objects.create(
            organization=self.organization,
            user=self.user,
            image=receipt_image("verified-receipt.png"),
            vendor_name="Old Receipt Store",
            total_amount="125.00",
            receipt_date=receipt_date,
            category="OFFICE",
            description="Verified OCR receipt",
            status="VERIFIED",
        )

    def test_ocr_expense_without_explicit_date_uses_today(self):
        receipt = self.create_verified_receipt(date(2020, 1, 15))

        response = self.client.post(f"/api/receipts/{receipt.id}/create_expense/", {})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        expense = Expense.objects.get(id=response.data["expense_id"])
        self.assertEqual(expense.date, timezone.localdate())

    def test_ocr_expense_does_not_default_to_old_detected_receipt_date(self):
        old_receipt_date = date(2018, 7, 4)
        receipt = self.create_verified_receipt(old_receipt_date)

        response = self.client.post(f"/api/receipts/{receipt.id}/create_expense/", {})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        expense = Expense.objects.get(id=response.data["expense_id"])
        self.assertNotEqual(expense.date, old_receipt_date)
        receipt.refresh_from_db()
        self.assertEqual(receipt.receipt_date, old_receipt_date)

    @patch('expenses.views.ExpenseViewSet.check_budgets_for_expense')
    def test_owner_receipt_expense_triggers_budget_check(self, check_budgets):
        receipt = self.create_verified_receipt(date.today())

        response = self.client.post(f'/api/receipts/{receipt.id}/create_expense/', {})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        expense = Expense.objects.get(id=response.data['expense_id'])
        self.assertEqual(expense.status, 'APPROVED')
        check_budgets.assert_called_once_with(expense)

    @patch('analytics.views.detect_expense_anomalies')
    @patch('receipts.views.notify_pending_approval')
    def test_staff_receipt_expense_notifies_owner(self, notify_pending, detect_anomaly):
        detect_anomaly.return_value = {
            'expense_id': 1,
            'score': 65,
            'severity': 'MEDIUM',
            'reasons': [{'code': 'HIGH_CATEGORY_AMOUNT', 'message': 'Higher than usual.'}],
        }
        staff = User.objects.create_user(
            username='receiptstaff',
            email='receipt-staff@example.com',
            password='StrongPass123!',
            email_verified=True,
        )
        OrganizationMember.objects.create(
            user=staff,
            organization=self.organization,
            role='STAFF',
        )
        staff.active_organization = self.organization
        staff.save(update_fields=['active_organization'])
        receipt = Receipt.objects.create(
            organization=self.organization,
            user=staff,
            image=receipt_image('staff-receipt.png'),
            vendor_name='Staff Store',
            total_amount='75.00',
            receipt_date=date.today(),
            category='OFFICE',
            status='VERIFIED',
        )
        self.client.force_authenticate(staff)

        response = self.client.post(f'/api/receipts/{receipt.id}/create_expense/', {})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        expense = Expense.objects.get(id=response.data['expense_id'])
        self.assertEqual(expense.status, 'PENDING')
        notify_pending.assert_called_once()
        owners, notified_expense = notify_pending.call_args.args
        self.assertEqual(notified_expense, expense)
        self.assertEqual(list(owners.values_list('user_id', flat=True)), [self.user.id])
        unusual = Notification.objects.get(
            user=self.user,
            notification_type='UNUSUAL_EXPENSE',
            related_object_id=expense.id,
        )
        self.assertEqual(unusual.metadata['anomaly_score'], 65)
        self.assertEqual(unusual.metadata['severity'], 'MEDIUM')


def receipt_image(name="receipt.png", content_type="image/png"):
    output = io.BytesIO()
    Image.new("RGB", (8, 8), color="white").save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type=content_type)


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    AI_RECEIPT_SCAN_ENABLED=True,
    GEMINI_API_KEY="test-gemini-key",
    GEMINI_RECEIPT_MODEL="gemini-2.5-flash",
    OCR_QUEUE_FALLBACK_SYNC=True,
)
class ReceiptGeminiUploadTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="receiptuser",
            email="receipt@example.com",
            password="StrongPass123!",
            email_verified=True,
        )
        self.organization = Organization.objects.create(name="Receipt Org")
        self.other_organization = Organization.objects.create(name="Other Receipt Org")
        OrganizationMember.objects.create(user=self.user, organization=self.organization, role="OWNER")
        OrganizationMember.objects.create(user=self.user, organization=self.other_organization, role="STAFF")
        self.user.active_organization = self.organization
        self.user.save(update_fields=["active_organization"])
        self.client.force_authenticate(self.user)

    def test_missing_file_returns_400(self):
        response = self.client.post(
            "/api/receipts/",
            {},
            format="multipart",
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image", response.data)
        self.assertFalse(Receipt.objects.exists())

    def test_invalid_file_type_is_rejected(self):
        response = self.client.post(
            "/api/receipts/",
            {"image": SimpleUploadedFile("receipt.txt", b"not an image", content_type="text/plain")},
            format="multipart",
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image", response.data)
        self.assertFalse(Receipt.objects.exists())

    @override_settings(GEMINI_API_KEY="")
    def test_missing_gemini_api_key_returns_clear_error(self):
        response = self.client.post(
            "/api/receipts/",
            {"image": receipt_image()},
            format="multipart",
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "AI receipt scanning is not configured. Add GEMINI_API_KEY or enter the expense manually.",
        )
        self.assertFalse(Receipt.objects.exists())

    def test_upload_processes_with_gemini_and_uses_active_organization_header(self):
        extracted = {
            "vendor": "Header Store",
            "amount": 245.75,
            "date": "2026-06-20",
            "category": "OFFICE",
            "notes": "Office supplies",
            "confidence": 0.86,
            "raw_text": "Header Store Total 245.75",
        }

        with patch("receipts.tasks.process_receipt_ocr.delay", side_effect=OperationalError("broker down")) as delay:
            with patch("receipts.tasks.GeminiReceiptExtractor.extract", return_value=extracted):
                response = self.client.post(
                    "/api/receipts/",
                    {"image": receipt_image()},
                    format="multipart",
                    HTTP_X_ORGANIZATION_ID=str(self.other_organization.id),
                )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["queue_mode"], "sync")
        delay.assert_not_called()
        self.assertEqual(response.data["scan"]["vendor"], "Header Store")
        self.assertEqual(response.data["scan"]["amount"], 245.75)
        self.assertEqual(response.data["scan"]["date"], "2026-06-20")
        receipt = Receipt.objects.get(id=response.data["id"])
        self.assertEqual(receipt.organization, self.other_organization)
        self.assertEqual(receipt.user, self.user)
        self.assertEqual(receipt.ocr_provider, "gemini")
        self.assertEqual(receipt.ocr_model, "gemini-2.5-flash")


class GeminiReceiptExtractorTestCase(TestCase):
    def test_parser_and_normalizer_handle_valid_json(self):
        extractor = GeminiReceiptExtractor()
        payload = extractor._parse_json_response(
            """
            {
              "vendor": "Cafe Central",
              "amount": "Rs. 1,250.50",
              "date": "June 21, 2026",
              "category": "Food & Dining",
              "notes": "Client lunch",
              "confidence": 0.91,
              "raw_text": "Cafe Central Grand Total Rs. 1,250.50"
            }
            """
        )

        result = extractor.normalize(payload)

        self.assertEqual(result["vendor"], "Cafe Central")
        self.assertEqual(result["amount"], 1250.50)
        self.assertEqual(result["date"], "2026-06-21")
        self.assertEqual(result["category"], "FOOD")
        self.assertEqual(result["notes"], "Client lunch")
        self.assertEqual(result["confidence"], 0.91)
        self.assertIn("Grand Total", result["raw_text"])

    def test_malformed_model_output_is_handled_safely(self):
        extractor = GeminiReceiptExtractor()

        with self.assertRaises(AIReceiptExtractionError) as error:
            extractor._parse_json_response("not json at all")

        self.assertEqual(
            str(error.exception),
            "AI receipt scanning failed. Try a clearer image or enter the expense manually.",
        )

    @override_settings(
        AI_RECEIPT_SCAN_ENABLED=True,
        GEMINI_API_KEY="test-gemini-key",
        GEMINI_RECEIPT_MODEL="gemini-2.5-flash",
    )
    def test_extract_returns_exact_scan_shape(self):
        model_text = """
        {
          "vendor": "Exact Mart",
          "amount": 99.99,
          "date": "2026-06-22",
          "category": "OFFICE",
          "notes": "Printer paper",
          "confidence": 0.8,
          "raw_text": "Exact Mart Total 99.99"
        }
        """

        with patch.object(GeminiReceiptExtractor, "_call_gemini", return_value=model_text):
            result = GeminiReceiptExtractor().extract(receipt_image())

        self.assertEqual(
            set(result.keys()),
            {"vendor", "amount", "date", "category", "notes", "confidence", "raw_text"},
        )
        self.assertEqual(result["vendor"], "Exact Mart")
        self.assertEqual(result["amount"], 99.99)
        self.assertEqual(result["date"], "2026-06-22")
        self.assertEqual(result["category"], "OFFICE")
