"""
Punctuator - Post-processing punctuation restoration for speech recognition output.

Adds punctuation (commas, periods, question marks, etc.) to raw text from
Google Web Speech API, which returns unpunctuated text.

Supports Chinese (zh) and English (en).
"""

import re


# ──────────────────────────── Chinese ────────────────────────────

# Words that typically end a clause (insert comma after)
_ZH_CLAUSE_ENDERS = {
    "的", "了", "地", "得", "着", "过", "是", "在", "有", "不", "没",
    "也", "都", "就", "还", "又", "才", "而", "及", "或", "但", "等",
    "吧", "呢", "啊", "嘛", "哦", "呀", "嗯",
    "说", "想", "觉得", "认为", "希望", "觉得",
    "时候", "之前", "之后", "期间", "同时",
    "因为", "所以", "虽然", "但是", "如果", "那么", "既然", "只要",
    "不过", "而且", "并且", "然后", "另外", "此外", "其实", "比如",
    "首先", "其次", "最后", "总之", "一般来说", "总的来说",
}

# Question markers - insert ? after
_ZH_QUESTION_MARKS = {"吗", "呢", "吧", "嘛"}

# Words that indicate a question
_ZH_QUESTION_INDICATORS = {
    "什么", "怎么", "为什么", "怎样", "怎么样", "哪里", "哪儿",
    "谁", "哪个", "哪些", "多少", "几", "几号",
    "是不是", "有没有", "能不能", "可不可以", "要不要", "好不好",
    "行不行", "对不对", "懂不懂", "知不知道", "明不明白",
}

# Exclamatory patterns
_ZH_EXCLAMATORY_PREFIX = {"多", "太", "真", "好", "真是", "真是", "多么"}
_ZH_EXCLAMATORY_SUFFIX = {"极了", "透了", "坏了", "死了", "得很"}

# Conjunctions that separate clauses (insert comma before)
_ZH_CONJUNCTIONS = {
    "但是", "不过", "然而", "可是", "只是", "另外", "此外",
    "而且", "并且", "然后", "接着", "所以", "因此", "于是",
    "因为", "虽然", "如果", "既然", "只要", "只有",
    "无论", "不管", "即使", "哪怕", "除非",
    "其实", "实际上", "事实上", "总的来说", "总之",
}

# Words that typically precede a colon (introducing explanation/list)
_ZH_COLON_WORDS = {"例如", "比如", "如下", "说是", "就是", "意思是", "原因是"}

# Pause particles - light pause
_ZH_PAUSE_PARTICLES = {"嗯", "啊", "呃", "那个", "这个", "就是", "然后"}


def add_punctuation_chinese(text: str) -> str:
    """Add punctuation to raw Chinese text using jieba segmentation + rules."""
    import jieba
    import jieba.posseg

    text = text.strip()
    if not text:
        return text

    # Already has some punctuation? Return as-is
    if any(p in text for p in "。，！？；：、…"):
        return text

    words = list(jieba.posseg.cut(text))
    if not words:
        return text

    # Convert pair objects to (word, flag) tuples
    words = [(w.word, w.flag) for w in words]

    result = []
    clause_length = 0  # characters since last punctuation

    for i, (word, flag) in enumerate(words):
        result.append(word)
        clause_length += len(word)

        # Don't add punctuation at the very end (handled separately)
        is_last = (i == len(words) - 1)
        if is_last:
            break

        next_word = words[i + 1][0] if i + 1 < len(words) else ""

        # ── Question mark ──
        if word in _ZH_QUESTION_MARKS and clause_length >= 3:
            result.append("？")
            clause_length = 0
            continue

        if word in _ZH_QUESTION_INDICATORS:
            # Look ahead - if this is near the end, add ?
            remaining = sum(len(w) for w, _ in words[i + 1:])
            if remaining <= 8:
                result.append("？")
                clause_length = 0
                continue

        # ── Comma before conjunctions ──
        if next_word in _ZH_CONJUNCTIONS and clause_length >= 4:
            result.append("，")
            clause_length = 0
            continue

        # ── Comma after clause enders ──
        if word in _ZH_CLAUSE_ENDERS and clause_length >= 6:
            result.append("，")
            clause_length = 0
            continue

        # ── Colon ──
        if word in _ZH_COLON_WORDS and next_word:
            result.append("：")
            clause_length = 0
            continue

        # ── Long clause → period ──
        if clause_length >= 20:
            result.append("。")
            clause_length = 0
            continue

        # ── Medium clause → comma ──
        if clause_length >= 12 and word in _ZH_CLAUSE_ENDERS:
            result.append("，")
            clause_length = 0
            continue

    # ── End of text: add period or question mark ──
    final_text = "".join(result)
    last_word = words[-1][0] if words else ""

    if last_word in _ZH_QUESTION_MARKS or last_word in _ZH_QUESTION_INDICATORS:
        # Remove trailing ? if we already added one
        if not final_text.endswith("？"):
            final_text += "？"
    elif final_text and final_text[-1] not in "。！？，；：":
        # Check for exclamatory
        if any(final_text.endswith(s) for s in _ZH_EXCLAMATORY_SUFFIX):
            final_text += "！"
        elif any(final_text.startswith(p) for p in _ZH_EXCLAMATORY_PREFIX):
            final_text += "！"
        else:
            final_text += "。"

    return final_text


# ──────────────────────────── English ────────────────────────────

# Transitional phrases that get a comma after
_EN_TRANSITIONS = {
    "however", "therefore", "moreover", "furthermore", "additionally",
    "in fact", "for example", "for instance", "in addition",
    "on the other hand", "as a result", "consequently", "meanwhile",
    "first", "second", "third", "finally", "lastly", "next", "then",
    "in conclusion", "in summary", "in short", "in other words",
    "above all", "after all", "as a matter of fact", "of course",
    "on the contrary", "in contrast", "for one thing",
}

# Coordinating conjunctions (comma before when joining clauses)
_EN_CONJUNCTIONS = {"but", "and", "or", "so", "yet", "for", "nor"}

# Question-starting words
_EN_QUESTION_STARTS = {
    "who", "what", "where", "when", "why", "how", "which", "whose",
    "is", "are", "was", "were", "do", "does", "did", "can", "could",
    "will", "would", "should", "may", "might", "have", "has", "had",
    "am", "shall", "ought",
}

# Common abbreviations (don't treat period as sentence end)
_EN_ABBREVS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "ave", "blvd",
    "inc", "ltd", "co", "corp", "vs", "etc", "approx", "dept",
    "est", "fig", "min", "max", "avg", "no",
}


# Words that strongly indicate a new sentence starts (if current clause is long enough)
_EN_SENTENCE_STARTERS = {
    "i", "we", "they", "you", "he", "she", "it",
    "this", "that", "these", "those",
    "there", "here",
    "my", "our", "your", "his", "her", "its", "their",
    "but", "however", "therefore", "moreover", "furthermore",
    "additionally", "first", "second", "third", "finally",
    "lastly", "next", "today", "yesterday", "tomorrow",
    "everyone", "nobody", "somebody", "anyone",
    "let", "please", "thank", "thanks",
    "speech", "machine", "artificial", "technology",
}

# Soft sentence starters (need longer preceding clause)
_EN_SOFT_STARTERS = {
    "the", "a", "an", "in", "on", "at", "by", "for", "with",
    "from", "to", "of", "about", "as", "when", "while",
    "after", "before", "because", "since", "although",
    "if", "unless", "once", "during",
}

# Prepositions and subordinating conjunctions that often get a comma before
_EN_COMMA_BEFORE = {
    "because", "although", "while", "whereas", "since", "if",
    "when", "after", "before", "unless", "once", "until",
    "so that", "in order", "even though", "even if",
}


def _detect_sentences(words):
    """Split word list into sentence groups based on heuristics."""
    if not words:
        return []

    sentences = []
    current = []
    current_lower = []

    for i, word in enumerate(words):
        wl = word.lower().rstrip(".,;:!?")
        current.append(word)
        current_lower.append(wl)

        is_last = (i == len(words) - 1)
        clause_len = len(current)

        if is_last:
            sentences.append(current)
            break

        next_wl = words[i + 1].lower().rstrip(".,;:!?")

        # Check for multi-word transitions that start a new sentence
        if clause_len >= 5:
            # Check if next 1-3 words form a transition
            next_two = " ".join(w.lower() for w in words[i + 1:i + 3])
            next_three = " ".join(w.lower() for w in words[i + 1:i + 4])

            if next_three in _EN_TRANSITIONS or next_two in _EN_TRANSITIONS or next_wl in _EN_TRANSITIONS:
                sentences.append(current)
                current = []
                current_lower = []
                continue

        # Strong sentence starter after a reasonable clause
        if clause_len >= 6 and next_wl in _EN_SENTENCE_STARTERS:
            sentences.append(current)
            current = []
            current_lower = []
            continue

        # Soft starter after a long clause
        if clause_len >= 10 and next_wl in _EN_SOFT_STARTERS:
            sentences.append(current)
            current = []
            current_lower = []
            continue

        # Force break on very long clauses
        if clause_len >= 15:
            sentences.append(current)
            current = []
            current_lower = []
            continue

    if current:
        sentences.append(current)

    return sentences


def _add_commas_sentence(words):
    """Add commas within a single sentence's word list."""
    result = []
    clause_len = 0

    for i, word in enumerate(words):
        result.append(word)
        clause_len += 1

        is_last = (i == len(words) - 1)
        if is_last:
            break

        next_word = words[i + 1].lower().rstrip(".,;:!?")

        # Comma before coordinating conjunctions
        if next_word in _EN_CONJUNCTIONS and clause_len >= 4:
            result.append(",")
            clause_len = 0
            continue

        # Comma before subordinating conjunctions
        if next_word in _EN_COMMA_BEFORE and clause_len >= 5:
            result.append(",")
            clause_len = 0
            continue

        # Comma after single-word transitions
        wl = word.lower().rstrip(".,;:!?")
        if wl in _EN_TRANSITIONS and clause_len <= 2:
            result.append(",")
            clause_len = 0
            continue

        # Medium clause → comma
        if clause_len >= 8:
            result.append(",")
            clause_len = 0
            continue

    return result


def add_punctuation_english(text: str) -> str:
    """Add punctuation to raw English text using rules."""
    text = text.strip()
    if not text:
        return text

    # Already has punctuation? Just capitalize and return
    if any(p in text for p in ".,!?;:"):
        if text:
            text = text[0].upper() + text[1:]
        return text

    words = text.split()
    if not words:
        return text

    # Detect if the whole text is a question
    first_word_lower = words[0].lower() if words else ""
    is_question = first_word_lower in _EN_QUESTION_STARTS

    # Split into sentences
    sentence_groups = _detect_sentences(words)

    # Process each sentence
    processed_sentences = []
    for group in sentence_groups:
        comma_words = _add_commas_sentence(group)
        sentence_text = " ".join(comma_words)

        # Fix spacing
        sentence_text = re.sub(r'\s+([,;:])', r'\1', sentence_text)

        # Capitalize first letter
        if sentence_text:
            sentence_text = sentence_text[0].upper() + sentence_text[1:]

        # Add end punctuation
        if sentence_text and sentence_text[-1] not in ".!?":
            # Check if this sentence is a question
            fw = sentence_text.split()[0].lower() if sentence_text.split() else ""
            if fw in _EN_QUESTION_STARTS and len(sentence_groups) == 1:
                sentence_text += "?"
            else:
                sentence_text += "."

        processed_sentences.append(sentence_text)

    output = " ".join(processed_sentences)

    # Fix any double spaces
    output = re.sub(r'\s{2,}', ' ', output).strip()

    return output


# ──────────────────────────── Dispatcher ────────────────────────────

def add_punctuation(text: str, lang_code: str = "en-US") -> str:
    """
    Add punctuation to raw speech recognition text.

    Args:
        text: Raw text from speech recognition (no punctuation)
        lang_code: Language code like 'en-US', 'zh-CN', etc.

    Returns:
        Text with punctuation added
    """
    if not text or not text.strip():
        return text

    lang = lang_code.split("-")[0].lower()

    if lang == "zh":
        return add_punctuation_chinese(text)
    elif lang == "en":
        return add_punctuation_english(text)
    else:
        # For other languages, apply English rules as a fallback
        return add_punctuation_english(text)


if __name__ == "__main__":
    # Test
    test_en = "the quick brown fox jumps over the lazy dog today is a beautiful sunny day I am testing a voice to text application to see how accurate it is speech recognition technology has improved significantly in recent years"
    test_zh = "你好这是一个语音转文字的测试今天天气很好阳光明媚我在测试语音识别的准确率看看转换效果如何"

    print("=== English ===")
    print(f"Input:  {test_en}")
    print(f"Output: {add_punctuation_english(test_en)}")
    print()
    print("=== Chinese ===")
    print(f"Input:  {test_zh}")
    print(f"Output: {add_punctuation_chinese(test_zh)}")
