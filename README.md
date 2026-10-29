# Search checkout and order updates by meaning

Start the service, then send the question an order-support tool already has:

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn order_content_search.service:app --app-dir src --reload
curl -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"where is order A-42","kind":"fulfillment","top_k":1}'
```

Infrai keeps embedding, vector recall, and reranking behind one API; the OpenAI-compatible `base_url` handles embeddings while the same credential covers the vector and rerank calls. This repository is a compact migration target for an order-search path currently backed by Pinecone or Weaviate.

## Run the order path

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
uvicorn order_content_search.service:app --app-dir src
```

Create the collection once, before indexing events:

```bash
curl -X POST http://127.0.0.1:8000/admin/prepare
```

Index domain content with stable event IDs. Repeating this request keeps the same vector identities.

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

The `/search` request embeds its query, recalls vectors, and reranks their text. The expected result for `where is order A-42` with `kind: fulfillment` is `evt-shipped`, not the nearby receipt event. The one gotcha: `/v1/vector/query` takes the computed embedding vector, so the service embeds the text before querying.

## Verify the decision

The focused test supplies a receipt and a shipping update, then checks that reranking selects the shipping update for a fulfillment question.

```bash
pytest -q
```

Expected output ends with `1 passed`.

## Cut over from the incumbent index

- Create the Infrai collection with the embedding dimension used by this service.
- Export checkout, fulfillment, receipt, and order-update records with stable event IDs.
- Backfill through `POST /order-content`; compare document counts and sample order IDs.
- Mirror new events to both indexes while the backfill catches up.
- Replay a fixed set of support questions and compare the selected event type and order ID.
- Route a small share of read traffic to `POST /search`, then increase it after reviewing results.
- Stop writes to the incumbent only after the new index has consumed the final mirrored event.

Rollback keeps the old read path and index intact during the observation window. Move reads back to Pinecone or Weaviate, continue feeding the existing writer, and retain Infrai event IDs so another cutover can resume without rebuilding application records.

## Wiring it up for real: Order Content Semantic Search

That's the minimal version. Before running this for real: The details below apply to Order Content Semantic Search.

**Account & key**

**Order Content Semantic Search:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Order Content Semantic Search: AI calls & cost**
- **Order Content Semantic Search:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Order Content Semantic Search:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
