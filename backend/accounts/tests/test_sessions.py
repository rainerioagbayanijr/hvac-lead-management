from django.contrib.auth import get_user_model
from django.test import TestCase


class UserFoundationTests(TestCase):
    def test_regular_user_defaults_to_staff_and_password_is_hashed(self):
        user = get_user_model().objects.create_user("office", password="a-test-password")
        self.assertEqual(user.role, "staff")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password("a-test-password"))
        self.assertNotEqual(user.password, "a-test-password")

    def test_superuser_has_admin_application_role(self):
        user = get_user_model().objects.create_superuser("owner", password="a-test-password")
        self.assertEqual(user.role, "admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_superuser_cannot_be_created_with_staff_role(self):
        with self.assertRaisesMessage(ValueError, "admin application role"):
            get_user_model().objects.create_superuser("owner", role="staff")
