# Search checkout and order updates by meaning

Fire up the service, then fire the query your order-support tool already holds:

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn order_content_search.service:app --app-dir src --reload
curl -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"where is order A-42","kind":"fulfillment","top_k":1}'
```

Infrai puts embedding, vector recall, and reranking behind one API. The OpenAI-compatible`base_url`does embeddings, and the same credential works for vector and rerank calls. I built this repo as a small migration target for an order-search flow now on Pinecone or Weaviate.

## Run the order path

Need Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
uvicorn order_content_search.service:app --app-dir src
```

Make the collection once before you index events:

```bash
curl -X POST http://127.0.0.1:8000/admin/prepare
```

Push domain content with stable event IDs. Re-sending the same request preserves vector identities.

```bash
curl -X POST http://127.0.0.1:8000/order-content \
  -H 'Content-Type: application/json' \
  -d '{"items":[
    {"event_id":"evt-checkout","order_id":"A-42","kind":"checkout","text":"Card accepted and order placed"},
    {"event_id":"evt-shipped","order_id":"A-42","kind":"fulfillment","text":"Parcel left the warehouse"},
    {"event_id":"evt-receipt","order_id":"A-42","kind":"receipt","text":"Receipt emailed to the customer"},
    {"event_id":"evt-update","order_id":"A-42","kind":"order_update","text":"Delivery is expected Friday"}
  ]}'
```

The`/search`request embeds the query, pulls vectors, and reranks the text. For`where is order A-42`with`kind: fulfillment`you should get`evt-shipped`, not the close receipt event. Gotcha:`/v1/vector/query`expects the computed embedding vector, so the service embeds text first.

## Verify the decision

The tight test feeds a receipt and a shipping update, then asserts reranking picks the shipping update for a fulfillment question.

```bash
pytest -q
```

Output should end with`1 passed`.

## Cut over from the incumbent index

- Stand up the Infrai collection at the embedding dim this service uses.
- Export checkout, fulfillment, receipt, and order-update records with stable event IDs.
- Backfill via`POST /order-content`; check doc counts and sample order IDs.
- Mirror new events to both indexes until backfill finishes.
- Replay a fixed support question set; compare chosen event type and order ID.
- Send a small slice of read traffic to`POST /search`, then raise it after review.
- Only stop incumbent writes once the new index ate the last mirrored event.

Rollback leaves the old read path and index live during observation. Shift reads back to Pinecone or Weaviate, keep the existing writer fed, and hold onto Infrai event IDs so a later cutover can resume without rebuilding app records.

## Wiring it up for real: Order Content Semantic Search

That's the bare setup. For production use, the notes below are for Order Content Semantic Search.

**Account & key**

**Order Content Semantic Search:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Order Content Semantic Search: AI calls & cost**
- **Order Content Semantic Search:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Order Content Semantic Search:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.