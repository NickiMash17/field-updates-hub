from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Comment, FieldUpdate, Reaction, UpdateAuditLog, UserProfile


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
        UserProfile.objects.filter(user=self.user).update(team_name="North", role="field_agent")
        UserProfile.objects.filter(user=self.other_user).update(team_name="South", role="field_agent")

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
                "status": "open",
                "visibility": "public",
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

    def test_feed_status_filter_returns_only_matching_status(self):
        FieldUpdate.objects.create(
            author=self.user,
            title="Still open task",
            content="Pending inspection",
            category="general",
            status="open",
        )
        resolved = FieldUpdate.objects.create(
            author=self.user,
            title="Fixed issue",
            content="Completed successfully",
            category="general",
            status="resolved",
        )
        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.get(reverse("updates:feed"), {"status": "resolved"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["updates"]), [resolved])

    def test_feed_visibility_rules_show_public_team_and_own_private(self):
        same_team_user = User.objects.create_user(
            username="farmer3",
            email="farmer3@example.com",
            password="StrongPass123!",
        )
        UserProfile.objects.filter(user=same_team_user).update(team_name="North", role="field_agent")

        public_post = FieldUpdate.objects.create(
            author=self.other_user,
            title="Public",
            content="Anyone can see",
            category="general",
            visibility="public",
        )
        team_post = FieldUpdate.objects.create(
            author=same_team_user,
            title="North team",
            content="North only",
            category="general",
            visibility="team",
        )
        own_private = FieldUpdate.objects.create(
            author=self.user,
            title="My private",
            content="My notes",
            category="general",
            visibility="private",
        )
        hidden_private = FieldUpdate.objects.create(
            author=self.other_user,
            title="Hidden private",
            content="Do not show",
            category="general",
            visibility="private",
        )
        hidden_team = FieldUpdate.objects.create(
            author=self.other_user,
            title="South team",
            content="South only",
            category="general",
            visibility="team",
        )

        self.client.login(username="farmer1", password="StrongPass123!")
        response = self.client.get(reverse("updates:feed"))
        updates = list(response.context["updates"])

        self.assertIn(public_post, updates)
        self.assertIn(team_post, updates)
        self.assertIn(own_private, updates)
        self.assertNotIn(hidden_private, updates)
        self.assertNotIn(hidden_team, updates)

    def test_manager_can_edit_and_delete_other_users_update(self):
        UserProfile.objects.filter(user=self.other_user).update(role="manager", team_name="South")
        update = FieldUpdate.objects.create(
            author=self.user,
            title="Managed post",
            content="Needs supervisor edit",
            category="general",
        )
        self.client.login(username="farmer2", password="StrongPass123!")

        edit_response = self.client.post(
            reverse("updates:edit", args=[update.pk]),
            {
                "title": "Manager edited",
                "content": "Manager changed content",
                "category": "general",
                "status": "in_progress",
                "visibility": "team",
            },
        )
        self.assertRedirects(edit_response, reverse("updates:feed"))
        update.refresh_from_db()
        self.assertEqual(update.title, "Manager edited")
        self.assertEqual(update.status, "in_progress")

        delete_response = self.client.post(reverse("updates:delete", args=[update.pk]))
        self.assertRedirects(delete_response, reverse("updates:feed"))
        self.assertFalse(FieldUpdate.objects.filter(pk=update.pk).exists())

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
                "status": "in_progress",
                "visibility": "team",
                "is_pinned": "on",
            },
        )
        self.assertRedirects(response, reverse("updates:feed"))
        update.refresh_from_db()
        self.assertEqual(update.title, "Updated title")
        self.assertEqual(update.category, "crop")
        self.assertEqual(update.status, "in_progress")
        self.assertEqual(update.visibility, "team")
        self.assertTrue(update.is_pinned)

    def test_feed_post_can_add_comment_to_update(self):
        update = FieldUpdate.objects.create(
            author=self.user,
            title="Needs attention",
            content="Check irrigation line",
            category="general",
        )
        self.client.login(username="farmer2", password="StrongPass123!")

        response = self.client.post(
            reverse("updates:feed"),
            {
                "action": "add_comment",
                "update_id": update.pk,
                "comment_content": "I can take a look this afternoon.",
            },
        )

        self.assertRedirects(response, reverse("updates:feed"))
        comment = Comment.objects.get(update=update)
        self.assertEqual(comment.author, self.other_user)
        self.assertEqual(comment.content, "I can take a look this afternoon.")

    def test_feed_post_toggle_reaction_creates_updates_and_removes_reaction(self):
        update = FieldUpdate.objects.create(
            author=self.user,
            title="Storm warning",
            content="Heavy rain expected",
            category="weather",
        )
        self.client.login(username="farmer2", password="StrongPass123!")

        create_response = self.client.post(
            reverse("updates:feed"),
            {
                "action": "toggle_reaction",
                "update_id": update.pk,
                "reaction_type": "urgent",
            },
        )
        self.assertRedirects(create_response, reverse("updates:feed"))
        reaction = Reaction.objects.get(update=update, user=self.other_user)
        self.assertEqual(reaction.reaction_type, "urgent")

        update_response = self.client.post(
            reverse("updates:feed"),
            {
                "action": "toggle_reaction",
                "update_id": update.pk,
                "reaction_type": "support",
            },
        )
        self.assertRedirects(update_response, reverse("updates:feed"))
        reaction.refresh_from_db()
        self.assertEqual(reaction.reaction_type, "support")

        remove_response = self.client.post(
            reverse("updates:feed"),
            {
                "action": "toggle_reaction",
                "update_id": update.pk,
                "reaction_type": "support",
            },
        )
        self.assertRedirects(remove_response, reverse("updates:feed"))
        self.assertFalse(Reaction.objects.filter(update=update, user=self.other_user).exists())

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
                "status": "resolved",
                "visibility": "public",
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

    def test_audit_log_created_for_create_edit_delete_comment_and_reaction(self):
        self.client.login(username="farmer1", password="StrongPass123!")
        create_response = self.client.post(
            reverse("updates:feed"),
            {
                "title": "Audit target",
                "content": "Track every action",
                "category": "general",
                "status": "open",
                "visibility": "public",
            },
        )
        self.assertRedirects(create_response, reverse("updates:feed"))
        update = FieldUpdate.objects.get(title="Audit target")

        self.assertTrue(UpdateAuditLog.objects.filter(field_update=update, action="create", actor=self.user).exists())

        edit_response = self.client.post(
            reverse("updates:edit", args=[update.pk]),
            {
                "title": "Audit target updated",
                "content": "Track every action",
                "category": "general",
                "status": "resolved",
                "visibility": "team",
            },
        )
        self.assertRedirects(edit_response, reverse("updates:feed"))
        self.assertTrue(UpdateAuditLog.objects.filter(field_update=update, action="edit").exists())
        self.assertTrue(UpdateAuditLog.objects.filter(field_update=update, action="status_change").exists())

        comment_response = self.client.post(
            reverse("updates:feed"),
            {
                "action": "add_comment",
                "update_id": update.pk,
                "comment_content": "Audit comment",
            },
        )
        self.assertRedirects(comment_response, reverse("updates:feed"))
        self.assertTrue(UpdateAuditLog.objects.filter(field_update=update, action="comment_add").exists())

        reaction_response = self.client.post(
            reverse("updates:feed"),
            {
                "action": "toggle_reaction",
                "update_id": update.pk,
                "reaction_type": "ack",
            },
        )
        self.assertRedirects(reaction_response, reverse("updates:feed"))
        self.assertTrue(UpdateAuditLog.objects.filter(field_update=update, action="reaction_toggle").exists())

        delete_response = self.client.post(reverse("updates:delete", args=[update.pk]))
        self.assertRedirects(delete_response, reverse("updates:feed"))
        self.assertTrue(
            UpdateAuditLog.objects.filter(action="delete", update_title_snapshot="Audit target updated").exists()
        )
