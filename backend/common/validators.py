import re
from rest_framework import serializers

# Regex patterns for URL and open redirect detection
URL_PATTERN = re.compile(
    r"(?:https?://|www\.|(?:\b[a-z0-9-]+\.(?:com|org|net|xyz|app|io|ru|cc|tk|me|info|biz|live|top|site|vip)\b))",
    re.IGNORECASE,
)

GOOGLE_SHARE_PATTERN = re.compile(
    r"(?:share\.google|drive\.google|google\.com/share)",
    re.IGNORECASE,
)

# Explicit casino, gambling, and betting keywords
CASINO_GAMBLING_PATTERN = re.compile(
    r"\b(?:casino|casinos|slot|slots|poker|roulette|blackjack|baccarat|betting|bet365|bookmaker|jackpot)\b",
    re.IGNORECASE,
)

# Obvious promotional, monetary advertising, and voucher spam
PROMO_MONETARY_PATTERN = re.compile(
    r"(?:\$\s*\d+|\d+\s*\$|\b\d{3,}\s*(?:usd|eur|gbp)\b|\b(?:promocode|promocodes|promo\s+code|promo\s+codes|bonus\s+code|bonus\s+codes|deposit\s+bonus|free\s+spins|cashback|free\s+money|get\s+bonus|claim\s+bonus|welcome\s+bonus)\b)",
    re.IGNORECASE,
)

# Repeated characters (e.g., 'aaaaaa' or '!!!!!!')
REPEATED_CHARS_PATTERN = re.compile(r"(.)\1{4,}")

# Symbols / digits only (i.e. contains no alphabetic letters)
NO_LETTERS_PATTERN = re.compile(r"^[^a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]+$")


def validate_employer_or_company_name(name: str, field_label: str = "Name") -> str:
    """
    Validates employer full_name or company name to prevent promotional spam,
    bot injections, casino ads, and malicious links.

    Preserves legitimate company names (e.g., '1Password', '3M', 'AT&T', 'A-1 Tech LLC', 'Yahoo!').
    """
    if not name:
        return name

    # 1. Normalize whitespace
    cleaned = " ".join(name.strip().split())

    # 2. Length limits
    if len(cleaned) < 2:
        raise serializers.ValidationError(f"{field_label} must be at least 2 characters long.")
    if len(cleaned) > 100:
        raise serializers.ValidationError(f"{field_label} cannot exceed 100 characters.")

    # 3. Reject URLs and Google Share links
    if URL_PATTERN.search(cleaned) or GOOGLE_SHARE_PATTERN.search(cleaned):
        raise serializers.ValidationError(
            f"{field_label} cannot contain website URLs or web links."
        )

    # 4. Reject casino and gambling advertising
    if CASINO_GAMBLING_PATTERN.search(cleaned):
        raise serializers.ValidationError(
            f"{field_label} cannot contain casino, gambling, or betting terms."
        )

    # 5. Reject promotional and monetary advertising
    if PROMO_MONETARY_PATTERN.search(cleaned):
        raise serializers.ValidationError(
            f"{field_label} cannot contain promotional codes, bonus offers, or monetary advertising."
        )

    # 6. Reject excessive repeated characters
    if REPEATED_CHARS_PATTERN.search(cleaned):
        raise serializers.ValidationError(
            f"{field_label} cannot contain excessively repeated characters."
        )

    # 7. Reject names consisting only of numbers or punctuation symbols
    if NO_LETTERS_PATTERN.match(cleaned):
        raise serializers.ValidationError(
            f"{field_label} must contain at least one letter."
        )

    return cleaned


def validate_candidate_name(name: str, field_label: str = "Full name") -> str:
    """
    Validates candidate full_name to prevent spam accounts, automated bot injections,
    URLs, promotional advertising, and garbage strings while preserving legitimate
    international personal names.

    Preserves legitimate names such as:
    - 'John Doe'
    - 'Mary-Jane Watson'
    - "O'Connor"
    - 'René Müller'
    - 'José García'
    - 'Jean-Luc Picard'
    - 'Anne Marie'
    - 'Li Wei'
    - 'A. Kumar'
    """
    if not name or not name.strip():
        raise serializers.ValidationError(f"{field_label} is required.")

    # 1. Normalize leading, trailing, and repeated whitespace
    cleaned = " ".join(name.strip().split())

    # 2. Length limits: 2 to 80 characters
    if len(cleaned) < 2:
        raise serializers.ValidationError(f"{field_label} must be at least 2 characters long.")
    if len(cleaned) > 80:
        raise serializers.ValidationError(f"{field_label} cannot exceed 80 characters.")

    # 3. Reject URLs and web links
    if URL_PATTERN.search(cleaned):
        raise serializers.ValidationError(
            f"{field_label} cannot contain website URLs or web links."
        )

    # 4. Reject Google Drive and Google sharing links
    if GOOGLE_SHARE_PATTERN.search(cleaned):
        raise serializers.ValidationError(
            f"{field_label} cannot contain website URLs or web links."
        )

    # 5. Reject promotional and monetary advertising
    if PROMO_MONETARY_PATTERN.search(cleaned):
        raise serializers.ValidationError(
            f"{field_label} cannot contain promotional codes, bonus offers, or monetary advertising."
        )

    # 6. Reject excessive repeated characters (5 or more consecutive identical characters)
    if REPEATED_CHARS_PATTERN.search(cleaned):
        raise serializers.ValidationError(
            f"{field_label} cannot contain excessively repeated characters."
        )

    # 7. Reject names consisting only of numbers or symbols
    if NO_LETTERS_PATTERN.match(cleaned):
        raise serializers.ValidationError(
            f"{field_label} must contain at least one letter."
        )

    return cleaned
