from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import FieldUpdate


class AuthAndFeedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="farmer1",
            email="farmer1@example.com",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="farmer2",
            email="farmer2@example.com",
            password="StrongPass123!",
        )

    def test_feed_requires_authentication(self):
        response = self.client.get(reverse("updates:feed"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_register_creates_user_and_redirects_to_feed(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newgrower",
                "email": "newgrower@example.com",
                "password1": "NewStrongPass123!",
                "password2": "NewStrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("updates:feed"))
        self.assertTrue(User.objects.filter(username="newgrower").exists())

        follow_response = self.client.get(reverse("updates:feed"))
        self.assertEqual(follow_response.status_code, 200)

    def test_create_update_sets_author_to_logged_in_user(self):
        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.post(
            reverse("updates:feed"),
            {
                "title": "Corn pests spotted",
                "content": "Saw pests on northern section.",
                "category": "pest",
            },
        )
        self.assertRedirects(response, reverse("updates:feed"))
        created = FieldUpdate.objects.get(title="Corn pests spotted")
        self.assertEqual(created.author, self.user)

    def test_feed_category_filter_returns_only_selected_category(self):
        FieldUpdate.objects.create(
            author=self.user,
            title="Rain incoming",
            content="Heavy rain forecast tonight.",
            category="weather",
        )
        FieldUpdate.objects.create(
            author=self.user,
            title="New fertilizer trial",
            content="Testing batch B.",
            category="fertilizer",
        )
        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.get(reverse("updates:feed"), {"category": "weather"})

        self.assertEqual(response.status_code, 200)
        updates = list(response.context["updates"])
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].category, "weather")

    def test_feed_search_filters_by_title_content_or_author(self):
        FieldUpdate.objects.create(
            author=self.user,
            title="Aphids detected",
            content="Lower leaves have clusters.",
            category="pest",
        )
        FieldUpdate.objects.create(
            author=self.other_user,
            title="Irrigation complete",
            content="Watering cycle finished.",
            category="general",
        )
        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.get(reverse("updates:feed"), {"q": "aphids"})

        self.assertEqual(response.status_code, 200)
        updates = list(response.context["updates"])
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].title, "Aphids detected")

    def test_feed_paginates_results(self):
        for i in range(12):
            FieldUpdate.objects.create(
                author=self.user,
                title=f"Update {i}",
                content="Batch post",
                category="general",
            )
        self.client.login(username="farmer1", password="StrongPass123!")

        first_page = self.client.get(reverse("updates:feed"))
        second_page = self.client.get(reverse("updates:feed"), {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(list(first_page.context["updates"])), 10)
        self.assertEqual(len(list(second_page.context["updates"])), 2)
        self.assertEqual(first_page.context["page_obj"].number, 1)
        self.assertEqual(second_page.context["page_obj"].number, 2)

    def test_feed_shows_pinned_updates_first(self):
        regular = FieldUpdate.objects.create(
            author=self.user,
            title="Regular update",
            content="Standard post",
            category="general",
        )
        pinned = FieldUpdate.objects.create(
            author=self.user,
            title="Pinned update",
            content="Important note",
            category="general",
            is_pinned=True,
        )
        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.get(reverse("updates:feed"))

        updates = list(response.context["updates"])
        self.assertEqual(updates[0].pk, pinned.pk)
        self.assertEqual(updates[1].pk, regular.pk)

    def test_feed_extracts_hashtags_and_filters_by_tag(self):
        tagged = FieldUpdate.objects.create(
            author=self.user,
            title="Weather watch #Urgent",
            content="Rain band approaching #NorthField",
            category="weather",
        )
        untagged = FieldUpdate.objects.create(
            author=self.user,
            title="General note",
            content="No hashtag here",
            category="general",
        )
        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.get(reverse("updates:feed"), {"tag": "urgent"})

        tagged.refresh_from_db()
        self.assertSetEqual(set(tagged.tags.values_list("name", flat=True)), {"urgent", "northfield"})
        self.assertEqual(list(response.context["updates"]), [tagged])
        self.assertNotIn(untagged, list(response.context["updates"]))

    def test_feed_advanced_filters_by_author_pinned_and_date(self):
        old_post = FieldUpdate.objects.create(
            author=self.user,
            title="Old pinned",
            content="Old item #archive",
            category="general",
            is_pinned=True,
        )
        other_post = FieldUpdate.objects.create(
            author=self.other_user,
            title="Other user post",
            content="Current item",
            category="general",
            is_pinned=True,
        )

        old_date = timezone.now() - timedelta(days=10)
        FieldUpdate.objects.filter(pk=old_post.pk).update(created_at=old_date)
        old_post.refresh_from_db()

        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.get(
            reverse("updates:feed"),
            {
                "author": "farmer2",
                "pinned": "only",
                "from_date": (timezone.now() - timedelta(days=2)).date().isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["updates"]), [other_post])

    def test_owner_can_edit_update(self):
        update = FieldUpdate.objects.create(
            author=self.user,
            title="Old title",
            content="Old content",
            category="general",
        )
        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.post(
            reverse("updates:edit", args=[update.pk]),
            {
                "title": "Updated title",
                "content": "Updated content",
                "category": "crop",
                "is_pinned": "on",
            },
        )
        self.assertRedirects(response, reverse("updates:feed"))
        update.refresh_from_db()
        self.assertEqual(update.title, "Updated title")
        self.assertEqual(update.category, "crop")
        self.assertTrue(update.is_pinned)

    def test_non_owner_cannot_edit_update(self):
        update = FieldUpdate.objects.create(
            author=self.user,
            title="Protected title",
            content="Protected content",
            category="general",
        )
        self.client.login(username="farmer2", password="StrongPass123!")
        response = self.client.post(
            reverse("updates:edit", args=[update.pk]),
            {
                "title": "Attempted overwrite",
                "content": "No permission",
                "category": "crop",
            },
        )
        self.assertEqual(response.status_code, 403)
        update.refresh_from_db()
        self.assertEqual(update.title, "Protected title")

    def test_owner_can_delete_update(self):
        update = FieldUpdate.objects.create(
            author=self.user,
            title="To delete",
            content="Delete me",
            category="general",
        )
        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.post(reverse("updates:delete", args=[update.pk]))
        self.assertRedirects(response, reverse("updates:feed"))
        self.assertFalse(FieldUpdate.objects.filter(pk=update.pk).exists())

    def test_non_owner_cannot_delete_update(self):
        update = FieldUpdate.objects.create(
            author=self.user,
            title="Cannot delete",
            content="Protected post",
            category="general",
        )
        self.client.login(username="farmer2", password="StrongPass123!")
        response = self.client.post(reverse("updates:delete", args=[update.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(FieldUpdate.objects.filter(pk=update.pk).exists())

    def test_profile_context_includes_post_count(self):
        FieldUpdate.objects.create(
            author=self.user,
            title="First post",
            content="One",
            category="general",
        )
        FieldUpdate.objects.create(
            author=self.user,
            title="Second post",
            content="Two",
            category="weather",
        )
        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.get(reverse("updates:profile", args=[self.user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["post_count"], 2)
