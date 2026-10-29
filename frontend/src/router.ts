import { useEffect, useState } from "react";

/**
 * Định tuyến bằng hash: "#/" trang chủ, "#/s/<id>" không gian làm việc của một phiên,
 * "#/sus" phiếu đánh giá SUS, "#/sus/ket-qua" tổng hợp kết quả SUS.
 */
export type Route = { page: "home" } | { page: "session"; id: string } | { page: "sus" } | { page: "sus-results" };

export function parseRoute(hash: string): Route {
  if (hash.startsWith("#/sus/ket-qua")) return { page: "sus-results" };
  if (hash.startsWith("#/sus")) return { page: "sus" };
  const m = hash.match(/^#\/s\/([\w-]+)/);
  return m ? { page: "session", id: m[1] } : { page: "home" };
}

export function navigate(route: Route): void {
  location.hash = route.page === "session" ? `#/s/${route.id}`
    : route.page === "sus" ? "#/sus" : route.page === "sus-results" ? "#/sus/ket-qua" : "#/";
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
