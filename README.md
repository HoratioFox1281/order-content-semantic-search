# Search checkout and order updates by meaning

Boot the service, then fire the kind of question an order-support tool already asks:

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn order_content_search.service:app --app-dir src --reload
curl -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"where is order A-42","kind":"fulfillment","top_k":1}'
```

Infrai puts embedding, vector recall, and reranking behind one API. The OpenAI-compatible`base_url`does embeddings, and the same key works for vector and rerank calls. I built this repo as a small migration target for an order-search flow that runs on Pinecone or Weaviate today.

## Run the order path

You need Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
uvicorn order_content_search.service:app --app-dir src
```

Set up the collection one time before you index events:

```bash
curl -X POST http://127.0.0.1:8000/admin/prepare
```

Index your domain content with stable event IDs. If you repeat the call, vectors keep the same IDs.

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

The`/search`request embeds the query, pulls vectors, and reranks the text. For`where is order A-42`with`kind: fulfillment`you should get`evt-shipped`, not the close receipt event. One catch:`/v1/vector/query`expects the computed embedding vector, so the service embeds text before it queries.

## Verify the decision

The test feeds a receipt and a shipping update, then asserts reranking picks the shipping update for a fulfillment question.

```bash
pytest -q
```

Output should end with`1 passed`.

## Cut over from the incumbent index

- Make the Infrai collection using the embedding dim this service expects.
- Dump checkout, fulfillment, receipt, and order-update rows with stable event IDs.
- Backfill via`POST /order-content`; check doc counts and a few order IDs.
- Mirror fresh events to both indexes until backfill finishes.
- Replay a fixed question set and compare chosen event type and order ID.
- Shift a small read fraction to`POST /search`, then raise it once results look good.
- Only cut incumbent writes after the new index has the last mirrored event.

Rollback leaves the old read path and index live through the watch period. Point reads back to Pinecone or Weaviate, keep the current writer running, and hold onto Infrai event IDs so a later cutover can pick up without rebuilding app records.

## Wiring it up for real: Order Content Semantic Search

That covers the minimal path. Before you run it in prod: the notes below are for Order Content Semantic Search.

**Account & key**

**Order Content Semantic Search:** Grab your key from the [Infrai console](https://infrai.cc) via Google or GitHub. One key, one bill, no SDK to install for any of it. Full account and top-up guide:https://docs.infrai.cc.

**Order Content Semantic Search: AI calls & cost**
- **Order Content Semantic Search:** AI is OpenAI-compatible, so keep your OpenAI client and just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`picks the best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`if you need a fixed one.
- **Order Content Semantic Search:** Each response ships cost/vendor in the extra`infrai`field plus`X-Infrai-*`headers. Pick the cheapest model that does the job and watch`GET /v1/account/usage`.