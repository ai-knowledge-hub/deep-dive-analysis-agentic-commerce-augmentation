import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { isMockAuthEnabled } from "./lib/auth-mode";

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"]);

const authMiddleware = isMockAuthEnabled()
  ? function mockAuthMiddleware() {
      return NextResponse.next();
    }
  : clerkMiddleware((auth, req) => {
      if (!isPublicRoute(req)) {
        auth().protect();
      }
    });

export default authMiddleware;

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
