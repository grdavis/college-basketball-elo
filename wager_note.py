"""Optional daily note for the GitHub Pages predictions page.

Asks Gemini which games are worth considering a wager on. A missing API key
or any failed call returns None so the daily job still publishes the page.

This follows grdavis/transcript-summarizer: secret GEMINI_API_KEY, optional
GEMINI_MODELS / GEMINI_MODEL, and the same default model aliases
(gemini-flash-latest, then gemini-flash-lite-latest). That repo calls
google.genai. The daily workflow here is pinned to Python 3.8.15, and
google-genai 2.10.0 requires Python >= 3.10, so this module posts to the
same generateContent REST method with requests. The key is sent in the
x-goog-api-key header and is never printed.
"""

import html
import os
import time
from urllib.parse import quote

import requests

REPO_URL = "https://github.com/grdavis/college-basketball-elo"
INTRO_SENTENCE = (
	"Check out the full college-basketball-elo repository on GitHub to see methodology and more."
)

# Same aliases transcript-summarizer uses when GEMINI_MODELS is unset.
DEFAULT_MODELS = ("gemini-flash-latest", "gemini-flash-lite-latest")
# Short note, so cap the HTTP call well under the Actions job limit.
DEFAULT_HTTP_TIMEOUT_MS = 60000
MAX_ATTEMPTS = 2
MAX_NOTE_CHARS = 900
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{0}:generateContent"


def intro_markdown(daily_note=None):
	"""Intro block for docs/index.md, with the repo name linked."""
	sentence = (
		"Check out the full [college-basketball-elo]({0}) repository on GitHub to see methodology and more."
	).format(REPO_URL)
	parts = [sentence]
	note = (daily_note or "").strip()
	if note:
		parts.append(note)
	return "\n\n".join(parts) + "\n\n"


def intro_box_html(daily_note=None):
	"""Blue intro box: the repo sentence, then the optional daily note."""
	sentence = (
		'Check out the full <a href="{0}">college-basketball-elo</a> repository on GitHub to see methodology and more.'
	).format(REPO_URL)
	paragraphs = ["<p>{0}</p>".format(sentence)]
	note = (daily_note or "").strip()
	if note:
		for block in note.split("\n\n"):
			flat = " ".join(block.split())
			if flat:
				paragraphs.append("<p>{0}</p>".format(html.escape(flat)))
	inner = "\n        ".join(paragraphs)
	return '    <div class="info">\n        {0}\n    </div>'.format(inner)


def write_daily_note(predictions_df, rankings_df, date_str=None):
	"""Return a short wager note, or None when there is nothing to publish.

	Never raises. The daily job publishes the page either way.
	"""
	try:
		return _write_daily_note(predictions_df, rankings_df, date_str)
	except Exception as exc:
		print("Daily wager note skipped: {0}".format(type(exc).__name__))
		return None


def _write_daily_note(predictions_df, rankings_df, date_str):
	api_key = os.environ.get("GEMINI_API_KEY", "").strip()
	if not api_key:
		print("Daily wager note skipped: GEMINI_API_KEY is not set")
		return None

	ranks = _rank_lookup(rankings_df)
	game_lines = _games_table(predictions_df, ranks)
	if not game_lines:
		print("Daily wager note skipped: no games with a live spread")
		return None

	prompt = _prompt(date_str, _top10_line(rankings_df), game_lines)
	text = _generate(prompt, api_key)
	note = _clean_note(text)
	if not note:
		print("Daily wager note skipped: Gemini call failed")
		return None
	print("Daily wager note added ({0} characters)".format(len(note)))
	return note


def _model_list():
	raw = os.environ.get("GEMINI_MODELS", "").strip()
	if raw:
		models = [part.strip() for part in raw.split(",") if part.strip()]
		if models:
			return models
	legacy = os.environ.get("GEMINI_MODEL", "").strip()
	if legacy:
		return [legacy]
	return list(DEFAULT_MODELS)


def _timeout_seconds():
	raw = os.environ.get("GEMINI_HTTP_TIMEOUT_MS", "").strip()
	if not raw:
		return DEFAULT_HTTP_TIMEOUT_MS / 1000.0
	try:
		timeout_ms = int(raw)
	except ValueError:
		print("Daily wager note: ignoring invalid GEMINI_HTTP_TIMEOUT_MS")
		return DEFAULT_HTTP_TIMEOUT_MS / 1000.0
	if timeout_ms <= 0:
		print("Daily wager note: ignoring invalid GEMINI_HTTP_TIMEOUT_MS")
		return DEFAULT_HTTP_TIMEOUT_MS / 1000.0
	return timeout_ms / 1000.0


def _endpoint(model):
	return _ENDPOINT.format(quote(model, safe=""))


def _generate(prompt, api_key):
	headers = {
		"Content-Type": "application/json",
		"x-goog-api-key": api_key,
	}
	body = {
		"contents": [{"role": "user", "parts": [{"text": prompt}]}],
		"generationConfig": {"temperature": 0.4, "maxOutputTokens": 512},
	}
	timeout = _timeout_seconds()
	models = _model_list()
	for index, model in enumerate(models):
		for attempt in range(1, MAX_ATTEMPTS + 1):
			print("Daily wager note: requesting {0} (attempt {1})".format(model, attempt))
			try:
				response = requests.post(
					_endpoint(model),
					headers=headers,
					json=body,
					timeout=timeout,
				)
			except requests.RequestException as exc:
				print("Daily wager note: {0} hit {1}".format(model, type(exc).__name__))
				if attempt < MAX_ATTEMPTS:
					time.sleep(2 * attempt)
					continue
				break
			if response.status_code == 200:
				try:
					payload = response.json()
				except ValueError:
					print("Daily wager note: {0} returned a non-JSON response".format(model))
					break
				text, finish = _text_from_response(payload)
				if text:
					if finish == "MAX_TOKENS":
						text = _trim_to_sentence(text)
					return text
				print("Daily wager note: {0} returned an empty response".format(model))
				break
			print("Daily wager note: {0} returned HTTP {1}".format(model, response.status_code))
			if response.status_code in (401, 403):
				return None
			if response.status_code not in TRANSIENT_STATUS or attempt >= MAX_ATTEMPTS:
				break
			time.sleep(2 * attempt)
		if index + 1 < len(models):
			print("Daily wager note: falling back to {0}".format(models[index + 1]))
	return None


def _text_from_response(payload):
	candidates = payload.get("candidates") or []
	if not candidates or not isinstance(candidates[0], dict):
		return None, None
	candidate = candidates[0]
	finish = candidate.get("finishReason")
	content = candidate.get("content") or {}
	parts = content.get("parts") or []
	chunks = []
	for part in parts:
		if isinstance(part, dict) and part.get("text"):
			chunks.append(part["text"])
	text = "".join(chunks).strip()
	return (text or None), finish


def _clean_note(text):
	if not text:
		return None
	cleaned = _strip_fences(text.replace("\r\n", "\n").strip())
	lowered = cleaned.lower()
	for label in ("daily note:", "wager note:", "note:"):
		if lowered.startswith(label):
			cleaned = cleaned[len(label):].strip()
			break
	if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
		cleaned = cleaned[1:-1].strip()
	if len(cleaned) > MAX_NOTE_CHARS:
		cleaned = _trim_to_sentence(cleaned[:MAX_NOTE_CHARS])
	cleaned = cleaned.strip()
	if not cleaned:
		return None
	return cleaned


def _strip_fences(text):
	stripped = text.strip()
	if not stripped.startswith("```"):
		return stripped
	lines = stripped.split("\n")
	if lines and lines[0].startswith("```"):
		lines = lines[1:]
	if lines and lines[-1].strip().startswith("```"):
		lines = lines[:-1]
	return "\n".join(lines).strip()


def _trim_to_sentence(text):
	last = max(text.rfind("."), text.rfind("?"), text.rfind("!"))
	if last >= 40:
		return text[:last + 1].strip()
	return text.strip()


def _rank_lookup(rankings_df):
	ranks = {}
	if rankings_df is None:
		return ranks
	try:
		names = list(rankings_df["Team"])
	except Exception:
		return ranks
	for index, name in enumerate(names):
		ranks[_strip_star(name)] = index + 1
	return ranks


def _top10_line(rankings_df):
	try:
		names = list(rankings_df["Team"])[:10]
	except Exception:
		return ""
	return ", ".join("{0}. {1}".format(index + 1, name) for index, name in enumerate(names))


def _strip_star(name):
	text = str(name).strip()
	if text.endswith("*"):
		return text[:-1]
	return text


def _number(value):
	if value is None:
		return None
	text = str(value).strip()
	if text.lower() in ("", "nl", "n/a", "nan", "none", "pk", "even", "—", "-"):
		return None
	try:
		return float(text)
	except ValueError:
		return None


def _format_number(value):
	if value is None:
		return ""
	if abs(value - round(value)) < 1e-9:
		return str(int(round(value)))
	return str(round(value, 1))


def _site(value):
	if str(value).strip() in ("1", "1.0", "True", "true"):
		return "neutral"
	return "home"


def _games_table(predictions_df, ranks):
	lines = []
	for _, row in predictions_df.iterrows():
		vegas = _number(row["Live Away Spread"])
		if vegas is None:
			continue
		away = str(row["Away"])
		home = str(row["Home"])
		model = _number(row["Away Pred. Spread"])
		gap = _number(row["Abs. Pred. Diff."])
		if gap is None and model is not None:
			gap = round(abs(vegas - model), 1)
		away_rank = ranks.get(_strip_star(away), "")
		home_rank = ranks.get(_strip_star(home), "")
		lines.append(
			"{away} | {away_rank} | {away_prob} | {home} | {home_rank} | {home_prob} | {site} | {model} | {vegas} | {gap}".format(
				away=away,
				away_rank=away_rank,
				away_prob=row["Away Win Prob."],
				home=home,
				home_rank=home_rank,
				home_prob=row["Home Win Prob."],
				site=_site(row["Neutral"]),
				model=_format_number(model),
				vegas=_format_number(vegas),
				gap=_format_number(gap),
			)
		)
	return lines


def _prompt(date_str, top10, game_lines):
	header = (
		"Away | Away Elo rank | Away win% | Home | Home Elo rank | Home win% | "
		"Site | Model away spread | Vegas away spread | Gap"
	)
	table = "\n".join([header] + game_lines)
	return (
		"You write a short note for a college basketball predictions page about which "
		"games are worth considering a wager on.\n\n"
		"Write a few sentences a person can scan. Do not list every game. Plain prose "
		"only: no bullets, no headings, no markdown, no preamble, and no disclaimer paragraph.\n\n"
		"Spread sign: negative means that team is favored by that many points. Both spreads "
		"below are for the away team. Gap is the absolute difference between the model spread "
		"and the Vegas spread. A blank Elo rank means the team is outside the top 100. Say "
		"which side the model likes relative to the market, in plain language.\n\n"
		"Use your judgment. These are typical interesting spots, not a hard filter:\n"
		"- At least one of the two teams is in the Elo top 50.\n"
		"- The absolute gap between the model spread and the Vegas spread is 5 points or more.\n"
		"- The current Vegas absolute spread is under 12.5.\n"
		"Also mention a matchup of two Elo top-10 teams even when the gap is small.\n"
		"Games with no live Vegas spread are already omitted. Do not invent lines for them.\n"
		"A trailing * on a team name means the team is new to the model and its rating is thin.\n\n"
		"Date: {date}\n"
		"Elo top 10: {top10}\n\n"
		"Games:\n"
		"{table}\n"
	).format(
		date=date_str or "today",
		top10=top10 or "unavailable",
		table=table,
	)
