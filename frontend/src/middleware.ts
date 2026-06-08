import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
const isClerkConfigured = clerkKey && clerkKey !== "pk_test_placeholder" && !clerkKey.includes("placeholder");

const isProtectedRoute = createRouteMatcher([
  '/dashboard(.*)'
]);

let middlewareExport;
if (isClerkConfigured) {
  middlewareExport = clerkMiddleware(async (auth, req) => {
    if (isProtectedRoute(req)) {
      await auth.protect();
    }
  });
} else {
  // Pass-through for local development/testing without auth keys
  middlewareExport = () => NextResponse.next();
}

export default middlewareExport;


export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
};
