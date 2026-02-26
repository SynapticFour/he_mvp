// SPDX-License-Identifier: Apache-2.0
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const STORAGE_KEY = "securecollab_user_email";

type EmailContextType = {
  email: string | null;
  setEmail: (email: string) => void;
  isReady: boolean;
};

const EmailContext = createContext<EmailContextType | null>(null);

export function EmailProvider({ children }: { children: React.ReactNode }) {
  const [email, setEmailState] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    setEmailState(stored);
    setIsReady(true);
  }, []);

  const setEmail = useCallback((value: string) => {
    const trimmed = value.trim();
    setEmailState(trimmed);
    if (typeof window !== "undefined") localStorage.setItem(STORAGE_KEY, trimmed);
  }, []);

  return (
    <EmailContext.Provider value={{ email, setEmail, isReady }}>
      {children}
    </EmailContext.Provider>
  );
}

export function useEmail() {
  const ctx = useContext(EmailContext);
  if (!ctx) throw new Error("useEmail must be used within EmailProvider");
  return ctx;
}
