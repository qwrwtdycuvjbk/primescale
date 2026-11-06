export const URL_REGEX = /(?:https?:\/\/|www\.|\b[a-z0-9-]+\.(?:com|org|net|xyz|app|io|ru|cc|tk|me|info|biz|live|top|site|vip)\b)/i;

export const GOOGLE_SHARE_REGEX = /(?:share\.google|drive\.google|google\.com\/share)/i;

export const CASINO_GAMBLING_REGEX = /\b(?:casino|casinos|slot|slots|poker|roulette|blackjack|baccarat|betting|bet365|bookmaker|jackpot)\b/i;

export const PROMO_MONETARY_REGEX = /(?:\$\s*\d+|\d+\s*\$|\b\d{3,}\s*(?:usd|eur|gbp)\b|\b(?:promocode|promocodes|promo\s+code|promo\s+codes|bonus\s+code|bonus\s+codes|deposit\s+bonus|free\s+spins|cashback|free\s+money|get\s+bonus|claim\s+bonus|welcome\s+bonus)\b)/i;

export const REPEATED_CHARS_REGEX = /(.)\1{4,}/;

export const NO_LETTERS_REGEX = /^[^a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]+$/;

export function validateEmployerOrCompanyName(
  name: string,
  fieldLabel = "Name"
): { isValid: boolean; error?: string; cleaned: string } {
  const trimmed = name ? name.trim() : "";
  const cleaned = trimmed.replace(/\s+/g, " ");

  if (!cleaned) {
    return { isValid: false, error: `${fieldLabel} is required.`, cleaned };
  }

  if (cleaned.length < 2) {
    return { isValid: false, error: `${fieldLabel} must be at least 2 characters long.`, cleaned };
  }

  if (cleaned.length > 100) {
    return { isValid: false, error: `${fieldLabel} cannot exceed 100 characters.`, cleaned };
  }

  if (URL_REGEX.test(cleaned) || GOOGLE_SHARE_REGEX.test(cleaned)) {
    return { isValid: false, error: `${fieldLabel} cannot contain website URLs or web links.`, cleaned };
  }

  if (CASINO_GAMBLING_REGEX.test(cleaned)) {
    return { isValid: false, error: `${fieldLabel} cannot contain casino, gambling, or betting terms.`, cleaned };
  }

  if (PROMO_MONETARY_REGEX.test(cleaned)) {
    return {
      isValid: false,
      error: `${fieldLabel} cannot contain promotional codes, bonus offers, or monetary advertising.`,
      cleaned,
    };
  }

  if (REPEATED_CHARS_REGEX.test(cleaned)) {
    return { isValid: false, error: `${fieldLabel} cannot contain excessively repeated characters.`, cleaned };
  }

  if (NO_LETTERS_REGEX.test(cleaned)) {
    return { isValid: false, error: `${fieldLabel} must contain at least one letter.`, cleaned };
  }

  return { isValid: true, cleaned };
}

export function validateCandidateName(
  name: string,
  fieldLabel = "Full name"
): { isValid: boolean; error?: string; cleaned: string } {
  const trimmed = name ? name.trim() : "";
  const cleaned = trimmed.replace(/\s+/g, " ");

  if (!cleaned) {
    return { isValid: false, error: `${fieldLabel} is required.`, cleaned };
  }

  if (cleaned.length < 2) {
    return { isValid: false, error: `${fieldLabel} must be at least 2 characters long.`, cleaned };
  }

  if (cleaned.length > 80) {
    return { isValid: false, error: `${fieldLabel} cannot exceed 80 characters.`, cleaned };
  }

  if (URL_REGEX.test(cleaned) || GOOGLE_SHARE_REGEX.test(cleaned)) {
    return { isValid: false, error: `${fieldLabel} cannot contain website URLs or web links.`, cleaned };
  }

  if (PROMO_MONETARY_REGEX.test(cleaned)) {
    return {
      isValid: false,
      error: `${fieldLabel} cannot contain promotional codes, bonus offers, or monetary advertising.`,
      cleaned,
    };
  }

  if (REPEATED_CHARS_REGEX.test(cleaned)) {
    return { isValid: false, error: `${fieldLabel} cannot contain excessively repeated characters.`, cleaned };
  }

  if (NO_LETTERS_REGEX.test(cleaned)) {
    return { isValid: false, error: `${fieldLabel} must contain at least one letter.`, cleaned };
  }

  return { isValid: true, cleaned };
}
