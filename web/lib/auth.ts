"use client";

import { useUser } from "@clerk/nextjs";
import { isMockAuthEnabled } from "./auth-mode";

export { isMockAuthEnabled };

const mockUser = {
  id: process.env.NEXT_PUBLIC_MOCK_USER_ID ?? "mock-user-local",
  firstName: process.env.NEXT_PUBLIC_MOCK_USER_FIRST_NAME ?? "Mock",
};

function useMockUser() {
  return {
    isLoaded: true,
    isSignedIn: true,
    user: mockUser,
  };
}

function useClerkUser() {
  return useUser();
}

export const useAppUser = isMockAuthEnabled() ? useMockUser : useClerkUser;
