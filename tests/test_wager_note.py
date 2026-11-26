"""Daily wager note: Gemini is optional, and the intro box stays short."""

import os
import re
import unittest
from unittest.mock import Mock, patch

import requests

import wager_note


def _frame(records):
	class Frame(object):
		def __init__(self, rows):
			self._rows = rows

		def __getitem__(self, key):
			return [row[key] for row in self._rows]

		def iterrows(self):
			for index, row in enumerate(self._rows):
				yield index, row

	return Frame(records)


def _rankings():
	names = ["Duke", "UConn", "Houston", "Arizona", "Florida", "Tennessee", "Iowa State", "Auburn", "Gonzaga", "Alabama"]
	names += ["Team {0}".format(i) for i in range(11, 101)]
	return _frame([{"Team": name, "Elo Rating": 2000 - i, "7 Day Change": 0} for i, name in enumerate(names)])


def _game(away, home, live, model=3.0, gap=1.0, neutral=0, away_prob="40%", home_prob="60%"):
	return {
		"Neutral": neutral,
		"Away": away,
		"Away Win Prob.": away_prob,
		"Away Pred. Spread": model,
		"Live Away Spread": live,
		"Home": home,
		"Home Win Prob.": home_prob,
		"Home Pred. Spread": -model if isinstance(model, float) else "",
		"Abs. Pred. Diff.": gap,
	}


def _ok_response(text="Duke at UConn is the game to watch.", finish="STOP"):
	response = Mock()
	response.status_code = 200
	response.json.return_value = {
		"candidates": [{
			"finishReason": finish,
			"content": {"parts": [{"text": text}]},
		}]
	}
	return response


class IntroTests(unittest.TestCase):
	def test_markdown_is_only_the_linked_sentence_without_a_note(self):
		text = wager_note.intro_markdown(None)
		self.assertIn("[college-basketball-elo](https://github.com/grdavis/college-basketball-elo)", text)
		self.assertIn(wager_note.INTRO_SENTENCE.replace("college-basketball-elo", "[college-basketball-elo](https://github.com/grdavis/college-basketball-elo)"), text)
		self.assertNotIn("ELO rating methodology", text)
		self.assertNotIn("Teams with *", text)
		self.assertNotIn("abbreviations", text)

	def test_markdown_puts_the_note_under_the_sentence(self):
		text = wager_note.intro_markdown("Watch Duke at UConn.")
		sentence_at = text.find("repository on GitHub")
		note_at = text.find("Watch Duke at UConn.")
		self.assertGreater(note_at, sentence_at)

	def test_html_box_keeps_the_sentence_as_a_repo_link(self):
		page = wager_note.intro_box_html(None)
		visible = re.sub(r"<[^>]+>", "", page)
		self.assertIn(wager_note.INTRO_SENTENCE, " ".join(visible.split()))
		self.assertIn('href="https://github.com/grdavis/college-basketball-elo"', page)
		self.assertEqual(page.count("<p>"), 1)
		self.assertNotIn("ELO rating methodology", page)
		self.assertNotIn("Interactive features", page)
		self.assertNotIn("Teams with *", page)

	def test_html_box_escapes_the_note_under_the_sentence(self):
		page = wager_note.intro_box_html('A <script>alert("x")</script> take.')
		self.assertLess(page.find("college-basketball-elo"), page.find("&lt;script&gt;"))
		self.assertNotIn("<script>", page)


class GeminiCallTests(unittest.TestCase):
	def setUp(self):
		self._saved = {
			key: os.environ.get(key)
			for key in ("GEMINI_API_KEY", "GEMINI_MODELS", "GEMINI_MODEL", "GEMINI_HTTP_TIMEOUT_MS")
		}
		os.environ["GEMINI_API_KEY"] = "super-secret-key"
		os.environ.pop("GEMINI_MODELS", None)
		os.environ.pop("GEMINI_MODEL", None)
		os.environ.pop("GEMINI_HTTP_TIMEOUT_MS", None)

	def tearDown(self):
		for key, value in self._saved.items():
			if value is None:
				os.environ.pop(key, None)
			else:
				os.environ[key] = value

	def _slate(self):
		return _frame([
			_game("Duke", "UConn", live=-2.0, model=-1.5, gap=0.5, neutral=1, away_prob="48%", home_prob="52%"),
			_game("Southern", "Nebraska", live=20.0, model=8.0, gap=12.0),
			_game("Memphis", "Penn State", live="NL", model=-0.4, gap="N/A"),
		])

	@patch("wager_note.time.sleep")
	@patch("wager_note.requests.post")
	def test_key_goes_in_the_header_and_not_the_url_or_logs(self, post, _sleep):
		post.return_value = _ok_response()
		with patch("sys.stdout") as stdout:
			note = wager_note.write_daily_note(self._slate(), _rankings(), "2026-11-26")
			logged = "".join(call.args[0] for call in stdout.write.call_args_list)
		self.assertEqual(note, "Duke at UConn is the game to watch.")
		url = post.call_args.args[0]
		headers = post.call_args.kwargs["headers"]
		prompt = post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
		self.assertIn("gemini-flash-latest", url)
		self.assertNotIn("super-secret-key", url)
		self.assertEqual(headers["x-goog-api-key"], "super-secret-key")
		self.assertNotIn("super-secret-key", logged)
		self.assertNotIn("super-secret-key", prompt)
		self.assertIn("not a hard filter", prompt)
		self.assertIn("Duke", prompt)
		self.assertIn("Southern", prompt)
		self.assertNotIn("Memphis", prompt)
		self.assertNotIn("Penn State", prompt)

	@patch("wager_note.requests.post")
	def test_missing_key_skips_the_call(self, post):
		os.environ.pop("GEMINI_API_KEY", None)
		note = wager_note.write_daily_note(self._slate(), _rankings(), "2026-11-26")
		self.assertIsNone(note)
		post.assert_not_called()

	@patch("wager_note.requests.post")
	def test_no_live_spreads_skips_the_call(self, post):
		slate = _frame([_game("Memphis", "Penn State", live="NL")])
		note = wager_note.write_daily_note(slate, _rankings(), "2026-11-26")
		self.assertIsNone(note)
		post.assert_not_called()

	@patch("wager_note.time.sleep")
	@patch("wager_note.requests.post")
	def test_transient_failure_falls_back_to_flash_lite(self, post, _sleep):
		failed = Mock(status_code=503)
		post.side_effect = [failed, failed, _ok_response("A shorter slate today.")]
		note = wager_note.write_daily_note(self._slate(), _rankings(), "2026-11-26")
		self.assertEqual(note, "A shorter slate today.")
		urls = [call.args[0] for call in post.call_args_list]
		self.assertEqual(len(urls), 3)
		self.assertIn("gemini-flash-lite-latest", urls[-1])

	@patch("wager_note.time.sleep")
	@patch("wager_note.requests.post")
	def test_request_error_returns_none(self, post, _sleep):
		post.side_effect = requests.ConnectionError("network down")
		with patch("sys.stdout") as stdout:
			note = wager_note.write_daily_note(self._slate(), _rankings(), "2026-11-26")
			logged = "".join(call.args[0] for call in stdout.write.call_args_list)
		self.assertIsNone(note)
		self.assertNotIn("super-secret-key", logged)
		self.assertIn("ConnectionError", logged)

	@patch("wager_note.requests.post")
	def test_rejected_key_does_not_try_the_fallback_model(self, post):
		post.return_value = Mock(status_code=401)
		note = wager_note.write_daily_note(self._slate(), _rankings(), "2026-11-26")
		self.assertIsNone(note)
		self.assertEqual(post.call_count, 1)

	@patch("wager_note.requests.post")
	def test_model_override_uses_gemini_models(self, post):
		os.environ["GEMINI_MODELS"] = "gemini-2.5-flash"
		post.return_value = _ok_response()
		wager_note.write_daily_note(self._slate(), _rankings(), "2026-11-26")
		self.assertIn("gemini-2.5-flash", post.call_args.args[0])
		self.assertNotIn("gemini-flash-latest", post.call_args.args[0])


if __name__ == "__main__":
	unittest.main()
