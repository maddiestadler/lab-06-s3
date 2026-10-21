
#!/bin/bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET EXPIRES"
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRES="$3"

mkdir -p books
FILE="books/${URL##*/}"
curl -fL "$URL" -o "$FILE"

if ! aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    aws s3 mb "s3://$BUCKET"
fi

aws s3 cp "$FILE" "s3://$BUCKET/" \
    --content-type "text/plain; charset=utf-8"

aws s3 presign "s3://$BUCKET/${FILE##*/}" \
    --expires-in "$EXPIRES"
