import { rewrite, next } from '@vercel/edge';

// Op het redesign-domein (wijn-overzicht-2) moet de root "/" de nieuwe
// Apple-redesign tonen (kelder.html). Een vercel.json-rewrite werkt hier
// niet, omdat statische bestanden (index.html) vóór rewrites worden
// geserveerd. Edge Middleware draait juist vóór de filesystem en kan de
// root daarom wél herschrijven. Op het hoofddomein blijft de oude app.
export const config = {
  matcher: '/',
};

export default function middleware(request: Request) {
  const host = request.headers.get('host') || '';
  if (host === 'wijn-overzicht-2.vercel.app') {
    return rewrite(new URL('/kelder.html', request.url));
  }
  return next();
}
