import os
import time
import json
import hashlib
import requests

SHOPEE_URL = os.getenv("SHOPEE_URL", "https://open-api.affiliate.shopee.com.br/graphql")
APP_ID = os.getenv("SHOPEE_APP_ID", "")
SECRET = os.getenv("SHOPEE_APP_SECRET", "")
KEYWORDS = [x.strip() for x in os.getenv("KEYWORDS", "eletronicos,casa,beleza,ferramentas").split(",") if x.strip()]
MIN_RATING = float(os.getenv("MIN_RATING", "4.5"))
MIN_SALES = int(os.getenv("MIN_SALES", "100"))
MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "5"))
SUB_IDS = [x.strip() for x in os.getenv("SHOPEE_SUB_IDS", "whatsapp,grupo-vendas").split(",") if x.strip()][:5]

def sign(payload: str, timestamp: int) -> str:
    return hashlib.sha256(f"{APP_ID}{timestamp}{payload}{SECRET}".encode()).hexdigest()

def call_shopee(query: str, variables=None):
    if not APP_ID or not SECRET:
        raise RuntimeError("Configure SHOPEE_APP_ID e SHOPEE_APP_SECRET nos Secrets do GitHub.")
    body = json.dumps({"query": query, "variables": variables or {}}, separators=(",", ":"), ensure_ascii=False)
    timestamp = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={APP_ID},Signature={sign(body, timestamp)},Timestamp={timestamp}",
    }
    response = requests.post(SHOPEE_URL, headers=headers, data=body, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return data.get("data", {})

def get_products(keyword):
    query = """
    query ProductOffers($keyword: String!, $page: Int!, $limit: Int!) {
      productOfferV2(keyword: $keyword, sortType: 5, page: $page, limit: $limit) {
        nodes {
          itemId
          productName
          productLink
          imageUrl
          priceMin
          priceMax
          commissionRate
          shopeeCommissionRate
          sellerCommissionRate
          sales
          ratingStar
        }
        pageInfo { hasNextPage }
      }
    }
    """
    data = call_shopee(query, {"keyword": keyword, "page": 1, "limit": 20})
    return data.get("productOfferV2", {}).get("nodes", [])

def make_affiliate_link(origin_url):
    query = """
    mutation GenerateShortLink($originUrl: String!, $subIds: [String]) {
      generateShortLink(input: {originUrl: $originUrl, subIds: $subIds}) {
        shortLink
      }
    }
    """
    data = call_shopee(query, {"originUrl": origin_url, "subIds": SUB_IDS})
    return data.get("generateShortLink", {}).get("shortLink", "")

def eligible(p):
    rating = float(p.get("ratingStar") or 0)
    sales = int(p.get("sales") or 0)
    return rating >= MIN_RATING and sales >= MIN_SALES and bool(p.get("productLink"))

def main():
    print("=== ROBO SHOPEE ===")
    print("Iniciando busca de ofertas...")
    candidates = []

    for keyword in KEYWORDS:
        print(f"Buscando: {keyword}")
        for product in get_products(keyword):
            if eligible(product):
                product["_keyword"] = keyword
                candidates.append(product)

    unique = {}
    for p in candidates:
        unique[str(p.get("itemId"))] = p

    products = list(unique.values())[:MAX_PRODUCTS]
    if not products:
        print("Nenhum produto passou pelos filtros.")
        return

    print(f"Encontrados {len(products)} produtos elegíveis.")

    for p in products:
        affiliate = make_affiliate_link(p["productLink"])
        p["affiliateLink"] = affiliate
        print("\n--- OFERTA ---")
        print(f"Produto: {p.get('productName')}")
        print(f"Preço: R$ {float(p.get('priceMin') or 0):.2f}")
        print(f"Avaliação: {p.get('ratingStar')}")
        print(f"Vendas: {p.get('sales')}")
        print(f"Link afiliado: {affiliate}")

if __name__ == "__main__":
    main()
