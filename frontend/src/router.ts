import { useEffect, useState } from "react";

/** Định tuyến bằng hash: "#/" trang chủ, "#/s/<id>" không gian làm việc của một phiên. */
export type Route = { page: "home" } | { page: "session"; id: string };

export function parseRoute(hash: string): Route {
  const m = hash.match(/^#\/s\/([\w-]+)/);
  return m ? { page: "session", id: m[1] } : { page: "home" };
}

export function navigate(route: Route): void {
  location.hash = route.page === "home" ? "#/" : `#/s/${route.id}`;
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(location.hash));
  useEffect(() => {
    const on = () => setRoute(parseRoute(location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}
