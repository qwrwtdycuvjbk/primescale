/**
 * Centralized Django REST Framework Authentication API Service for Next.js.
 * Maps to backend accounts/views.py endpoints created in Phase 3A & Phase 11.
 */

import { djangoApi, RequestOptions } from "./client";
import type { Profile, UserRole } from "@/lib/types";

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthResponse extends AuthTokens {
  user: Profile;
  created?: boolean;
}

export interface RegisterPayload {
  email: string;
  password?: string;
  full_name?: string;
  phone?: string | null;
  role: Extract<UserRole, "employer" | "candidate">;
}

export interface LoginPayload {
  email: string;
  password?: string;
}

export interface GoogleOAuthPayload {
  email: string;
  full_name?: string;
  role: Extract<UserRole, "employer" | "candidate">;
  id_token?: string;
}

export interface PasswordResetConfirmPayload {
  uid: string;
  token: string;
  new_password?: string;
}

export interface VerifyEmailPayload {
  uid: string;
  token: string;
}

export const djangoAuth = {
  /**
   * Registers a new candidate or employer account.
   * POST /api/v1/auth/register/
   */
  register(payload: RegisterPayload, options?: RequestOptions): Promise<AuthResponse> {
    return djangoApi.post<AuthResponse>("/api/v1/auth/register/", payload, options);
  },

  /**
   * Authenticates user via email and password.
   * POST /api/v1/auth/login/
   */
  login(payload: LoginPayload, options?: RequestOptions): Promise<AuthResponse> {
    return djangoApi.post<AuthResponse>("/api/v1/auth/login/", payload, options);
  },

  /**
   * Returns authenticated user profile details.
   * GET /api/v1/auth/me/
   */
  getCurrentUser(token?: string, options?: RequestOptions): Promise<Profile> {
    return djangoApi.get<Profile>("/api/v1/auth/me/", {
      ...options,
      token,
    });
  },

  /**
   * Generates a new access token using a refresh token.
   * POST /api/v1/auth/refresh/
   */
  refreshToken(refreshToken: string, options?: RequestOptions): Promise<AuthTokens> {
    return djangoApi.post<AuthTokens>(
      "/api/v1/auth/refresh/",
      { refresh: refreshToken },
      options,
    );
  },

  /**
   * Blacklists refresh token and logs user out.
   * POST /api/v1/auth/logout/
   */
  logout(refreshToken?: string, options?: RequestOptions): Promise<{ status: string; message: string }> {
    return djangoApi.post<{ status: string; message: string }>(
      "/api/v1/auth/logout/",
      { refresh: refreshToken || "" },
      options,
    );
  },

  /**
   * Requests a password reset / account claim link.
   * POST /api/v1/auth/password-reset/
   */
  requestPasswordReset(email: string, options?: RequestOptions): Promise<{ detail: string }> {
    return djangoApi.post<{ detail: string }>(
      "/api/v1/auth/password-reset/",
      { email },
      options,
    );
  },

  /**
   * Confirms password reset with secure token and sets new password.
   * POST /api/v1/auth/password-reset-confirm/
   */
  confirmPasswordReset(payload: PasswordResetConfirmPayload, options?: RequestOptions): Promise<AuthResponse> {
    return djangoApi.post<AuthResponse>(
      "/api/v1/auth/password-reset-confirm/",
      payload,
      options,
    );
  },

  /**
   * Verifies email with secure token.
   * POST /api/v1/auth/verify-email/
   */
  verifyEmail(payload: VerifyEmailPayload, options?: RequestOptions): Promise<{ detail: string; user: Profile }> {
    return djangoApi.post<{ detail: string; user: Profile }>(
      "/api/v1/auth/verify-email/",
      payload,
      options,
    );
  },

  /**
   * Resends verification email.
   * POST /api/v1/auth/resend-verification/
   */
  resendVerification(email: string, options?: RequestOptions): Promise<{ detail: string }> {
    return djangoApi.post<{ detail: string }>(
      "/api/v1/auth/resend-verification/",
      { email },
      options,
    );
  },

  /**
   * Google OAuth login or account linking with existing Django user.
   * POST /api/v1/auth/oauth/google/
   */
  googleLogin(payload: GoogleOAuthPayload, options?: RequestOptions): Promise<AuthResponse> {
    return djangoApi.post<AuthResponse>(
      "/api/v1/auth/oauth/google/",
      payload,
      options,
    );
  },
};
