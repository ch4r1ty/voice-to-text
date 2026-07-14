"""
Punctuator - Post-processing punctuation restoration for speech recognition output.

Adds punctuation (commas, periods, question marks, etc.) to raw text from
Google Web Speech API, which returns unpunctuated text.

Supports Chinese (zh) and English (en).

Strategy: conservative placement — only add punctuation where confidence is high.
"""

import re


# ═══════════════════════════ Chinese ═════════════════════════════

# Clause-ending particles — strong signal to insert comma/period
_ZH_COMMA_AFTER = {
    "了", "的", "地", "得", "着",
}

# Question particles
_ZH_QUESTION_PARTICLES = {"吗", "呢", "吧", "嘛"}

# Question indicator words (usually near end)
_ZH_QUESTION_WORDS = {
    "什么", "怎么", "为什么", "怎样", "怎么样", "哪里", "哪儿",
    "谁", "哪个", "哪些", "多少", "几",
    "是不是", "有没有", "能不能", "要不要", "好不好",
}

# Conjunctions — insert comma BEFORE these
_ZH_CONJ_BEFORE = {
    "但是", "不过", "然而", "可是", "而且", "并且", "然后",
    "所以", "因此", "于是", "因为", "虽然", "如果", "既然",
    "只要", "只有", "无论", "不管", "即使", "哪怕",
    "另外", "此外", "其实", "实际上",
}

# Sentence-final exclamatory suffixes
_ZH_EXCL_SUFFIX = {"极了", "透了", "坏了", "死了", "得很"}


def add_punctuation_chinese(text: str) -> str:
    """Add punctuation to raw Chinese text using jieba segmentation + rules."""
    import jieba
    import jieba.posseg

    text = text.strip()
    if not text:
        return text

    # Already has punctuation? Return as-is
    if any(p in text for p in "。，！？；：、…"):
        return text

    words = [(w.word, w.flag) for w in jieba.posseg.cut(text)]
    if not words:
        return text

    result = []
    clause_len = 0  # char count since last punctuation mark

    for i, (word, flag) in enumerate(words):
        result.append(word)
        clause_len += len(word)

        is_last = (i == len(words) - 1)
        if is_last:
            break

        next_word = words[i + 1][0] if i + 1 < len(words) else ""

        # ── Question particle → ？ ──
        if word in _ZH_QUESTION_PARTICLES and clause_len >= 3:
            result.append("？")
            clause_len = 0
            continue

        # ── Comma BEFORE conjunctions ──
        if next_word in _ZH_CONJ_BEFORE and clause_len >= 4:
            result.append("，")
            clause_len = 0
            continue

        # ── Clause-ending particles ──
        # Only add comma if the clause is long enough (>= 8 chars)
        if word in _ZH_COMMA_AFTER and clause_len >= 8:
            result.append("，")
            clause_len = 0
            continue

        # ── Very long clause → period ──
        if clause_len >= 25:
            result.append("。")
            clause_len = 0
            continue

        # ── Long clause with particle → comma ──
        if clause_len >= 15 and word in _ZH_COMMA_AFTER:
            result.append("，")
            clause_len = 0
            continue

    # ── Build final text ──
    final = "".join(result)
    last_word = words[-1][0] if words else ""

    # Add end punctuation
    if final and final[-1] not in "。！？，；：":
        if last_word in _ZH_QUESTION_PARTICLES or last_word in _ZH_QUESTION_WORDS:
            if not final.endswith("？"):
                final += "？"
        elif any(final.endswith(s) for s in _ZH_EXCL_SUFFIX):
            final += "！"
        else:
            final += "。"

    return final


# ═══════════════════════════ English ═════════════════════════════

# Strong sentence starters — high confidence new sentence
_EN_STRONG_STARTERS = {
    "i", "we", "they", "you", "he", "she",
    "but", "however", "therefore", "moreover", "furthermore",
    "first", "second", "third", "finally", "lastly",
    "let", "please", "thank", "thanks",
}

# Medium starters — need longer preceding clause
_EN_MEDIUM_STARTERS = {
    "it", "this", "that", "these", "those",
    "there", "here",
    "today", "yesterday", "tomorrow",
    "everyone", "nobody", "somebody",
    "my", "our", "your", "his", "her", "their",
}

# Soft starters — need even longer preceding clause
_EN_SOFT_STARTERS = {
    "the", "a", "an", "in", "on", "at",
    "when", "while", "after", "before",
    "artificial", "machine", "speech",
}

# Coordinating conjunctions — comma before (if clause is long enough)
_EN_CONJUNCTIONS = {"but", "and", "or", "so", "yet"}

# Transition words — comma after
_EN_TRANSITIONS = {
    "however", "therefore", "moreover", "furthermore", "additionally",
    "consequently", "meanwhile", "finally", "lastly", "next",
    "first", "second", "third", "then",
    "instead", "otherwise", "besides", "still", "also",
}

# Multi-word transitions
_EN_MULTI_TRANSITIONS = {
    "in fact", "for example", "for instance", "in addition",
    "on the other hand", "as a result", "in conclusion", "in summary",
    "in short", "in other words", "above all", "after all",
    "of course", "on the contrary", "in contrast",
}

# Question-starting words
_EN_QUESTION_STARTS = {
    "who", "what", "where", "when", "why", "how", "which", "whose",
    "is", "are", "was", "were", "do", "does", "did", "can", "could",
    "will", "would", "should", "may", "might", "have", "has", "had",
    "am", "shall",
}


def _detect_sentences_en(words):
    """Split word list into sentence groups based on heuristics."""
    if not words:
        return []

    sentences = []
    current = []

    for i, word in enumerate(words):
        current.append(word)
        clause_len = len(current)

        is_last = (i == len(words) - 1)
        if is_last:
            sentences.append(current)
            break

        next_wl = words[i + 1].lower().rstrip(".,;:!?")

        # Check multi-word transitions (2-3 words ahead)
        if clause_len >= 6:
            next_two = " ".join(w.lower() for w in words[i + 1:i + 3])
            next_three = " ".join(w.lower() for w in words[i + 1:i + 4])

            if next_three in _EN_MULTI_TRANSITIONS or next_two in _EN_MULTI_TRANSITIONS:
                sentences.append(current)
                current = []
                continue

        # Single-word transition as sentence starter
        if clause_len >= 6 and next_wl in _EN_TRANSITIONS:
            sentences.append(current)
            current = []
            continue

        # Strong starter (need at least 6 words in current clause)
        if clause_len >= 6 and next_wl in _EN_STRONG_STARTERS:
            sentences.append(current)
            current = []
            continue

        # Medium starter (need at least 8 words)
        if clause_len >= 8 and next_wl in _EN_MEDIUM_STARTERS:
            sentences.append(current)
            current = []
            continue

        # Soft starter (need at least 12 words)
        if clause_len >= 12 and next_wl in _EN_SOFT_STARTERS:
            sentences.append(current)
            current = []
            continue

        # Force break on very long clauses
        if clause_len >= 18:
            sentences.append(current)
            current = []
            continue

    return sentences


def _add_commas_en(words):
    """Add commas within a single sentence's word list. Conservative approach."""
    result = []
    clause_len = 0

    for i, word in enumerate(words):
        result.append(word)
        clause_len += 1

        is_last = (i == len(words) - 1)
        if is_last:
            break

        next_word = words[i + 1].lower().rstrip(".,;:!?")

        # Comma before coordinating conjunctions (only for longer clauses)
        if next_word in _EN_CONJUNCTIONS and clause_len >= 5:
            result.append(",")
            clause_len = 0
            continue

        # Comma after single-word transitions
        wl = word.lower().rstrip(".,;:!?")
        if wl in _EN_TRANSITIONS and clause_len <= 2:
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
    sentence_groups = _detect_sentences_en(words)

    # Process each sentence
    processed = []
    for group in sentence_groups:
        comma_words = _add_commas_en(group)
        sentence_text = " ".join(comma_words)

        # Fix spacing around punctuation
        sentence_text = re.sub(r'\s+([,;:])', r'\1', sentence_text)

        # Capitalize first letter
        if sentence_text:
            sentence_text = sentence_text[0].upper() + sentence_text[1:]

        # Add end punctuation
        if sentence_text and sentence_text[-1] not in ".!?":
            # Check if this specific sentence is a question
            fw = sentence_text.split()[0].lower() if sentence_text.split() else ""
            if fw in _EN_QUESTION_STARTS and len(group) <= 8:
                sentence_text += "?"
            else:
                sentence_text += "."

        processed.append(sentence_text)

    output = " ".join(processed)
    output = re.sub(r'\s{2,}', ' ', output).strip()

    return output


# ═══════════════════════════ Dispatcher ═════════════════════════════

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
        return add_punctuation_english(text)


if __name__ == "__main__":
    # Test with ground truth text (punctuation removed)
    test_en = "the quick brown fox jumps over the lazy dog today is a beautiful sunny day I am testing a voice to text application to see how accurate it is speech recognition technology has improved significantly in recent years machine learning models can now understand many languages and accents let us see how well this transcription works artificial intelligence is transforming the way we interact with computers thank you for watching this demonstration"
    test_zh = "你好这是一个语音转文字的测试今天天气很好阳光明媚我在测试语音识别的准确率看看转换效果如何科技改变生活人工智能正在快速发展希望这个工具能帮助你提高工作效率谢谢你的使用"
    test_en_q = "what time is it how are you doing today where is the nearest hospital"

    print("=== English (statements) ===")
    print(f"Input:  {test_en}")
    print(f"Output: {add_punctuation_english(test_en)}")
    print()
    print("=== English (questions) ===")
    print(f"Input:  {test_en_q}")
    print(f"Output: {add_punctuation_english(test_en_q)}")
    print()
    print("=== Chinese ===")
    print(f"Input:  {test_zh}")
    print(f"Output: {add_punctuation_chinese(test_zh)}")
    print()

    # Ground truth for comparison
    print("=== Ground Truth (English) ===")
    print("The quick brown fox jumps over the lazy dog. Today is a beautiful sunny day. I am testing a voice to text application to see how accurate it is. Speech recognition technology has improved significantly in recent years. Machine learning models can now understand many languages and accents. Let us see how well this transcription works. Artificial intelligence is transforming the way we interact with computers. Thank you for watching this demonstration.")
    print()
    print("=== Ground Truth (Chinese) ===")
    print("你好，这是一个语音转文字的测试。今天天气很好，阳光明媚。我在测试语音识别的准确率，看看转换效果如何。科技改变生活，人工智能正在快速发展。希望这个工具能帮助你提高工作效率。谢谢你的使用。")
