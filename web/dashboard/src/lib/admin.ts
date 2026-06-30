import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";

const STORAGE_KEY = "admin_mode";

/**
 * Detects admin mode from ?admin=true query param on mount.
 * Persists to sessionStorage so the flag survives tab navigation
 * without requiring the param in every URL.
 */
export function useAdminMode() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isAdmin, setIsAdmin] = useState<boolean>(
    () => sessionStorage.getItem(STORAGE_KEY) === "true",
  );

  // Check URL on mount only — if admin=true is present, persist and clean URL
  useEffect(() => {
    if (searchParams.get("admin") === "true") {
      sessionStorage.setItem(STORAGE_KEY, "true");
      setIsAdmin(true);
      const next = new URLSearchParams(searchParams);
      next.delete("admin");
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const enableAdmin = useCallback(() => {
    sessionStorage.setItem(STORAGE_KEY, "true");
    setIsAdmin(true);
  }, []);

  return { isAdmin, enableAdmin };
}
