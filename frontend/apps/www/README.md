To compile the frontend as standalone, run the following commands:

```bash
node run build
cp app/www/public/ app/www/.next/standalone/apps/www/ -r
cp app/www/.next/static/ -r .next/standalone/apps/www/.next
```
