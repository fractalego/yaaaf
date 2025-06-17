corepack enable pnpm
npm run build
cp apps/www/public/ apps/www/.next/standalone/apps/www/ -r
cp apps/www/.next/static/ apps/www/.next/standalone/apps/www/.next -r
cp apps/www/.next/standalone ../yaaf/client/ -r
