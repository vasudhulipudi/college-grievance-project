"""
Automated Pre-Submission Moderation & Anti-Abuse Engine
College Grievance and Facility Management System (CGMS)

This engine inspects, analyzes, scores, and classifies grievance submissions
BEFORE they are committed to the database or reach the Department Admin dashboard.

Sub-Engines:
1. Gibberish & Keyboard Mashing Detector
2. Profanity, Vulgarity & Abusive Harassment Detector (with Leet-Speak De-obfuscation)
3. Fraudulent Spam, Promotional Link & Placeholder Detector
"""

import re
import math
from collections import Counter

# ==============================================================================
# 1. PROFANITY, ABUSIVE HARASSMENT & VULGARITY CATALOG
# ==============================================================================

# Severe profanities and slurs that warrant immediate rejection (Score 80-100)
SEVERE_PROFANITIES = {
    'fuck', 'fucker', 'fucking', 'fucked', 'motherfucker', 'motherfucking',
    'shit', 'shitty', 'bullshit', 'shite',
    'bitch', 'bitches', 'bitching',
    'bastard', 'bastards',
    'asshole', 'assholes', 'dumbass', 'jackass',
    'cunt', 'cunts', 'dick', 'dicks', 'dickhead', 'cock', 'cocksucker',
    'pussy', 'whore', 'slut', 'nigger', 'nigga', 'faggot', 'chutiya',
    'madarchod', 'bhenchod', 'harami', 'kamina', 'gaand', 'randi', 'saala'
}

# Abusive, threatening, or hostile terms towards staff/students (Score 40-70)
ABUSIVE_HOSTILE_TERMS = {
    'idiot', 'idiots', 'moron', 'morons', 'stupid', 'imbecile',
    'corrupt', 'scoundrel', 'fraudster', 'useless piece', 'kill you',
    'burn the college', 'beat you', 'trash college', 'worst college ever',
    'go to hell', 'die', 'threaten', 'sabotage'
}

# Whitelist to safeguard against the Scunthorpe problem:
# These common academic and English words contain letter substrings that match profanity roots.
LEGITIMATE_WORD_WHITELIST = {
    'class', 'classes', 'classroom', 'classic', 'classical', 'classification',
    'assessment', 'assessments', 'assisting', 'assistance', 'assistant',
    'pass', 'passed', 'passage', 'passport', 'compass', 'trespass',
    'faculty', 'document', 'documents', 'documentation',
    'cockpit', 'peacock', 'hancock',
    'butter', 'button', 'shuttle', 'shift', 'sheet',
    'bitcharter', 'analysis', 'analytical', 'association', 'associates'
}

# Common Leet-speak replacement mappings
LEET_SUBS = {
    '@': 'a', '4': 'a',
    '8': 'b',
    '(': 'c',
    '3': 'e',
    '9': 'g',
    '1': 'i', '!': 'i', '|': 'i',
    '0': 'o',
    '$': 's', '5': 's',
    '7': 't', '+': 't',
    'v': 'u',
}

# ==============================================================================
# 2. KEYBOARD MASHING & GIBBERISH PATTERNS
# ==============================================================================

KEYBOARD_ROWS = [
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
    "1234567890",
    "poiuytrewq",
    "lkjhgfdsa",
    "mnbvcxz",
    "0987654321",
    "qazwsxedcrfv",
    "rfvtgbyhnujm"
]

COMMON_ENGLISH_WORDS = {
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for', 'not', 'on', 'with',
    'he', 'as', 'you', 'do', 'at', 'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
    'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what', 'so', 'up', 'out', 'if',
    'about', 'who', 'get', 'which', 'go', 'me', 'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him',
    'know', 'take', 'people', 'into', 'year', 'your', 'good', 'some', 'could', 'them', 'see', 'other',
    'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also', 'back', 'after', 'use',
    'two', 'how', 'our', 'work', 'first', 'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these',
    'give', 'day', 'most', 'us', 'water', 'fan', 'light', 'bench', 'room', 'hostel', 'lab', 'library',
    'canteen', 'food', 'teacher', 'faculty', 'exam', 'marks', 'syllabus', 'bus', 'transport', 'wifi',
    'internet', 'ac', 'cooler', 'broken', 'repair', 'issue', 'problem', 'clean', 'washroom', 'toilet',
    'drainage', 'electricity', 'power', 'projector', 'computer', 'system', 'mouse', 'keyboard', 'sports',
    'ground', 'cricket', 'urgent', 'maintenance', 'department', 'floor', 'block', 'college', 'student',
    'fee', 'notice', 'class', 'lecture', 'desk', 'door', 'window', 'leakage', 'smell', 'hygiene', 'help',
    'request', 'please', 'complaint', 'grievance', 'solve', 'action', 'soon', 'staff', 'admin', 'principal'
}

# ==============================================================================
# 3. SPAM & PLACEHOLDER PATTERNS
# ==============================================================================

MOCK_PLACEHOLDER_PHRASES = [
    r'^\s*test\s*$',
    r'^\s*testing\s*$',
    r'^\s*test\s+complaint\s*$',
    r'^\s*sample\s+complaint\s*$',
    r'^\s*dummy\s+complaint\s*$',
    r'^\s*please\s+ignore\s*$',
    r'^\s*fake\s+complaint\s*$',
    r'^\s*checking\s*$',
    r'^\s*asdf\s*$',
    r'^\s*qwerty\s*$',
    r'^\s*xyz\s*$',
    r'^\s*123\s*$',
    r'^\s*abc\s*$'
]

URL_PATTERN = re.compile(r'(https?:\/\/|www\.)[^\s]+|([a-zA-Z0-9-]+\.(com|org|net|xyz|biz|info|top|ru|cn|in|me|cc)\b)', re.IGNORECASE)

# ==============================================================================
# NORMALIZATION & TEXT UTILITIES
# ==============================================================================

def normalize_text_for_moderation(text: str) -> str:
    """Cleans text, preserves spaces, lowers casing, strips control chars."""
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', text.strip().lower())
    return cleaned

def deobfuscate_leet(text: str) -> str:
    """Replaces common leet-speak characters and removes intra-word dots/spaces."""
    res = text.lower()
    for symbol, char in LEET_SUBS.items():
        res = res.replace(symbol, char)
    
    # Collapse spaced letters e.g. "f u c k" -> "fuck", "s h i t" -> "shit"
    spaced_word_pattern = re.compile(r'\b([a-z])[ \.\-\*]+([a-z])[ \.\-\*]+([a-z])(?:[ \.\-\*]+([a-z]))?\b')
    def unspace(match):
        return "".join(g for g in match.groups() if g)
    res = spaced_word_pattern.sub(unspace, res)

    # Collapse consecutive identical letters > 2 e.g. "fuuuck" -> "fuck"
    res = re.sub(r'([a-z])\1{2,}', r'\1\1', res)
    return res

def calculate_shannon_entropy(text: str) -> float:
    """Computes Shannon entropy of character distribution."""
    if not text or len(text) <= 1:
        return 0.0
    counts = Counter(text)
    length = len(text)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

# ==============================================================================
# SUB-ENGINE 1: GIBBERISH & KEYBOARD MASHING
# ==============================================================================

def analyze_gibberish(text: str) -> dict:
    """
    Analyzes text for keyboard mashing, unpronounceable consonant clusters,
    abnormal vowel-consonant ratios, and meaningless repetitive tokens.
    """
    norm = normalize_text_for_moderation(text)
    if not norm:
        return {'score': 0, 'flagged': False, 'reasons': []}

    score = 0
    reasons = []

    # 1. Repetitive characters: e.g. "aaaaaaaa", "zzzzzzz", "11111111"
    repeat_char_match = re.findall(r'(.)\1{4,}', norm)
    if repeat_char_match:
        score += 45
        reasons.append(f'Excessive repeated characters detected ("{repeat_char_match[0] * 5}...")')

    # 2. Extract alphabetic tokens
    words = re.findall(r'[a-zA-Z]+', norm)
    if not words:
        if len(norm) > 4 and not any(c.isalnum() for c in norm):
            score += 70
            reasons.append('Text contains no recognizable words (only symbols)')
        return {'score': min(100, score), 'flagged': score >= 40, 'reasons': reasons}

    # 3. Check for keyboard sliding row sequences (e.g. asdfgh, qwertyuiop, zxcvbn)
    for row in KEYBOARD_ROWS:
        for length in [6, 5, 4]:
            for i in range(len(row) - length + 1):
                seq = row[i:i + length]
                if seq in norm:
                    score += 40
                    reasons.append(f'Keyboard row mashing sequence detected ("{seq}")')
                    break
            if score >= 40:
                break
        if score >= 60:
            break

    # 4. Consonant clustering & Vowel ratio per token
    vowels = set('aeiouy')
    unpronounceable_count = 0
    total_long_words = 0
    known_word_hits = 0

    for w in words:
        w_lower = w.lower()
        if len(w_lower) >= 4:
            total_long_words += 1
            if w_lower in COMMON_ENGLISH_WORDS:
                known_word_hits += 1
                continue

            num_vowels = sum(1 for c in w_lower if c in vowels)
            vowel_ratio = num_vowels / len(w_lower)

            # High consonant cluster (5 or more consecutive consonants)
            if re.search(r'[^aeiouy]{5,}', w_lower):
                unpronounceable_count += 1
            elif vowel_ratio < 0.12 and len(w_lower) >= 7:
                unpronounceable_count += 1
            elif vowel_ratio > 0.85 and len(w_lower) >= 6:
                unpronounceable_count += 1

    if total_long_words > 0:
        unpronounceable_ratio = unpronounceable_count / total_long_words
        if unpronounceable_ratio >= 0.5:
            score += 55
            reasons.append('High proportion of unpronounceable or non-lexical words')
        elif unpronounceable_ratio >= 0.25:
            score += 30
            reasons.append('Suspicious non-dictionary word patterns detected')

    # 5. Overly long continuous token (> 30 characters without space)
    long_words = [w for w in words if len(w) > 30]
    if long_words:
        score += 50
        reasons.append(f'Abnormally long continuous word token ({len(long_words[0])} characters)')

    # 6. Repetitive short words: e.g. "asdf asdf asdf asdf asdf"
    if len(words) >= 4:
        word_counts = Counter(w.lower() for w in words)
        most_common_word, count = word_counts.most_common(1)[0]
        if count / len(words) >= 0.65 and count >= 4 and most_common_word not in {'to', 'the', 'and', 'in', 'is'}:
            score += 45
            reasons.append(f'Excessive repetitive word looping ("{most_common_word}")')

    score = min(100, score)
    return {
        'score': score,
        'flagged': score >= 40,
        'reasons': reasons
    }

# ==============================================================================
# SUB-ENGINE 2: PROFANITY & ABUSIVE HARASSMENT
# ==============================================================================

def analyze_profanity(text: str) -> dict:
    """
    Analyzes text for profanity, obscenity, leet-speak obfuscation, and abusive hostility.
    Guaranteed zero false-positives for academic words on the whitelist.
    """
    if not text:
        return {'score': 0, 'flagged': False, 'severe': False, 'reasons': [], 'matches': []}

    score = 0
    reasons = []
    matches = []
    has_severe = False

    raw_lower = text.lower()
    deobf = deobfuscate_leet(text)

    def scan_for_terms(content_str: str, term_set: set, is_severe: bool):
        nonlocal score, has_severe
        for term in term_set:
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            found_matches = pattern.findall(content_str)
            if found_matches:
                filtered = []
                for m in found_matches:
                    if m.lower() not in LEGITIMATE_WORD_WHITELIST:
                        filtered.append(m)

                if filtered:
                    matches.extend(filtered)
                    if is_severe:
                        score += 85
                        has_severe = True
                        reasons.append(f'Prohibited severe profanity detected ("{term}")')
                    else:
                        score += 40
                        reasons.append(f'Disrespectful or abusive phrasing detected ("{term}")')

    scan_for_terms(raw_lower, SEVERE_PROFANITIES, is_severe=True)
    scan_for_terms(raw_lower, ABUSIVE_HOSTILE_TERMS, is_severe=False)

    if score < 85:
        scan_for_terms(deobf, SEVERE_PROFANITIES, is_severe=True)

    matches = list(set(matches))
    score = min(100, score)

    return {
        'score': score,
        'flagged': score >= 40,
        'severe': has_severe,
        'reasons': reasons,
        'matches': matches
    }

# ==============================================================================
# SUB-ENGINE 3: FRAUDULENT SPAM & PLACEHOLDERS
# ==============================================================================

def analyze_spam(title: str, description: str) -> dict:
    """
    Analyzes submission for spam, promotional links, placeholder/mock submissions,
    all-caps shouting, and low-effort empty content.
    """
    combined = f"{title} {description}".strip()
    score = 0
    reasons = []

    # 1. External URLs or promotional links
    url_matches = URL_PATTERN.findall(combined)
    if url_matches:
        score += 75
        reasons.append('External links or promotional URLs detected in grievance body')

    # 2. Placeholder or Mock grievance check
    for pattern in MOCK_PLACEHOLDER_PHRASES:
        if re.search(pattern, title, re.IGNORECASE) or re.search(pattern, description, re.IGNORECASE):
            score += 75
            reasons.append('Submission identified as a dummy or placeholder test complaint')
            break

    # 3. Excessive All-Caps Shouting (> 75% uppercase in string > 25 chars)
    alpha_chars = [c for c in combined if c.isalpha()]
    if len(alpha_chars) >= 25:
        uppercase_count = sum(1 for c in alpha_chars if c.isupper())
        if uppercase_count / len(alpha_chars) >= 0.75:
            score += 30
            reasons.append('Excessive all-caps text detected (unprofessional formatting)')

    # 4. Brevity & Substantive Information Threshold
    desc_clean = description.strip()
    if len(desc_clean) < 15:
        score += 35
        reasons.append('Description is too brief to convey actionable incident specifics')

    title_words = [w for w in re.findall(r'\b[a-zA-Z]{2,}\b', title)]
    if len(title_words) < 2:
        score += 25
        reasons.append('Title is incomplete (minimum 2 meaningful words required)')

    score = min(100, score)
    return {
        'score': score,
        'flagged': score >= 40,
        'reasons': reasons
    }

# ==============================================================================
# UNIFIED COMPOSITE MODERATION ENGINE
# ==============================================================================

def evaluate_content(title: str, description: str, category: str = '', student_id: int = None) -> dict:
    """
    Comprehensive evaluation function for grievance complaints.
    
    Returns structured decision dictionary:
    {
        'action': 'REJECT' | 'FLAG' | 'APPROVE',
        'overall_score': int (0-100),
        'is_blocked': bool,
        'is_flagged': bool,
        'is_clean': bool,
        'summary_status': 'Blocked' | 'Flagged' | 'Clean',
        'primary_reason': str,
        'all_reasons': list[str],
        'flags_csv': str,
        'categories': {
            'gibberish': {...},
            'profanity': {...},
            'spam': {...}
        },
        'suggestions': str
    }
    """
    title = (title or '').strip()
    description = (description or '').strip()
    combined_text = f"{title}\n{description}"

    gibberish_res = analyze_gibberish(combined_text)
    profanity_res = analyze_profanity(combined_text)
    spam_res = analyze_spam(title, description)

    if profanity_res['severe']:
        overall_score = max(85, profanity_res['score'])
    else:
        composite = (
            profanity_res['score'] * 0.40 +
            gibberish_res['score'] * 0.35 +
            spam_res['score'] * 0.25
        )
        max_subscore = max(profanity_res['score'], gibberish_res['score'], spam_res['score'])
        overall_score = int(max(composite, max_subscore * 0.9))

    overall_score = min(100, max(0, overall_score))

    all_reasons = []
    all_reasons.extend(profanity_res['reasons'])
    all_reasons.extend(gibberish_res['reasons'])
    all_reasons.extend(spam_res['reasons'])

    # Determine Action Tier
    if overall_score >= 70 or profanity_res['severe'] or gibberish_res['score'] >= 75 or spam_res['score'] >= 75:
        action = 'REJECT'
        summary_status = 'Blocked'
        is_blocked = True
        is_flagged = False
        is_clean = False
    elif overall_score >= 35 or gibberish_res['flagged'] or profanity_res['flagged'] or spam_res['flagged']:
        action = 'FLAG'
        summary_status = 'Flagged'
        is_blocked = False
        is_flagged = True
        is_clean = False
    else:
        action = 'APPROVE'
        summary_status = 'Clean'
        is_blocked = False
        is_flagged = False
        is_clean = True

    if all_reasons:
        primary_reason = all_reasons[0]
    else:
        primary_reason = "Grievance meets institutional quality and conduct standards."

    if action == 'REJECT':
        if profanity_res['severe']:
            suggestions = "Your submission contains prohibited abusive or profane language. Please revise your grievance using professional, respectful academic language."
        elif gibberish_res['score'] >= 70:
            suggestions = "Your submission appears to contain random keyboard typing or unreadable text. Please provide clear, meaningful sentences describing the issue."
        else:
            suggestions = "Your submission was identified as test or promotional spam. Please submit only genuine campus grievances with clear details."
    elif action == 'FLAG':
        suggestions = "Your grievance has been received but flagged for administrative review due to potential formatting, quality, or tone concerns."
    else:
        suggestions = "Submission verified. Meets institutional quality assurance criteria."

    flags_list = []
    if profanity_res['flagged']:
        flags_list.append(f"profanity:{profanity_res['score']}")
    if gibberish_res['flagged']:
        flags_list.append(f"gibberish:{gibberish_res['score']}")
    if spam_res['flagged']:
        flags_list.append(f"spam:{spam_res['score']}")
    flags_csv = ",".join(flags_list) if flags_list else "clean"

    return {
        'action': action,
        'overall_score': overall_score,
        'is_blocked': is_blocked,
        'is_flagged': is_flagged,
        'is_clean': is_clean,
        'summary_status': summary_status,
        'primary_reason': primary_reason,
        'all_reasons': all_reasons,
        'flags_csv': flags_csv,
        'categories': {
            'gibberish': gibberish_res,
            'profanity': profanity_res,
            'spam': spam_res
        },
        'suggestions': suggestions
    }
