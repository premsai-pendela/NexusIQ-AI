"""
Web Agent - Competitor Intelligence & Industry Data
Multi-source scraping: BeautifulSoup (static HTML) + JSON APIs + Shopify API

Production scrapers:
   - Newegg (BeautifulSoup) - Electronics
   - Goal Zero (Shopify API) - Electronics
   - IKEA (JSON API) - Home
   - Campmor (Shopify API) - Sports
   - Swanson (Shopify API) - Food/Supplements
   - NativePath (Shopify API) - Food/Supplements
   - Taylor Stitch, Chubbies, Finisterre (Shopify API) - Clothing

Features:
   - Smart caching (24-hour TTL)
   - Rate limiting
   - Explicit cached/live/sample data provenance
   - Optional sample fallback for demos only
   - Async parallel execution
"""

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import asyncio
import httpx
from bs4 import BeautifulSoup
import re
import time
import json
import logging
import threading
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import requests as req_lib  # For Campmor (httpx has encoding issues)

import sys
sys.path.append(str(Path(__file__).parent.parent))

from langchain_groq import ChatGroq
from config.settings import settings
from utils.llm_gateway import get_llm_gateway
from utils.quota_tracker import get_tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

quota_tracker = get_tracker()


# ═══════════════════════════════════════════════════════════
#  WEB AGENT CLASS
# ═══════════════════════════════════════════════════════════

class WebAgent:
    """
    Production web scraper with multiple strategies:
    - Shopify API (fastest, most reliable)
    - BeautifulSoup (static HTML sites)
    - JSON APIs (dynamic retail catalog sites)
    """
    
    # HTTP headers for BeautifulSoup requests
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }
    COMPETITOR_SCRAPER_METHODS = {
        "newegg": "_scrape_newegg",
        "goal zero": "_scrape_goalzero",
        "ikea": "_scrape_ikea_api",
        "taylor stitch": "_scrape_taylorstitch",
        "chubbies": "_scrape_chubbies",
        "finisterre": "_scrape_finisterre",
        "swanson": "_scrape_swanson",
        "nativepath": "_scrape_nativepath",
        "campmor": "_scrape_campmor",
    }
    CACHE_MAX_AGE_HOURS = 24
    STALE_CACHE_MAX_AGE_HOURS = 24 * 7
    
    def __init__(self):
        # HTTP client for BeautifulSoup scrapers
        self.client = httpx.Client(
            timeout=30.0,
            headers=self.HEADERS,
            follow_redirects=True
        )
        
        # Cache setup
        self.cache_file = Path("data/web_cache.json")
        self.cache_file.parent.mkdir(exist_ok=True)
        self.cache = self._load_cache()
        self._cache_lock = threading.RLock()
        
        # Groq LLM for answer generation
        if settings.groq_api_key:
            self.groq_client = ChatGroq(
                model=settings.groq_model,
                groq_api_key=settings.groq_api_key,
                temperature=0.3
            )
            logger.info("✅ Groq client initialized for Web Agent")
        else:
            self.groq_client = None
            logger.warning("⚠️  No Groq API key - Web Agent will return raw data only")
        self.llm_gateway = get_llm_gateway()
        
        logger.info("✅ Web Agent initialized")
    
    def _load_cache(self) -> Dict:
        """Load scraped data cache"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """Save scraped data cache"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def _cache_age_hours(self, cache_key: str) -> Optional[float]:
        cached = self.cache.get(cache_key)
        if not cached or not cached.get('timestamp'):
            return None
        try:
            cache_time = datetime.fromisoformat(cached['timestamp'])
        except (TypeError, ValueError):
            return None
        return max(0.0, (datetime.now() - cache_time).total_seconds() / 3600)

    def _should_scrape(self, cache_key: str, max_age_hours: int = CACHE_MAX_AGE_HOURS) -> bool:
        """Check if cache is fresh enough AND has actual data."""
        cached = self.cache.get(cache_key)
        if not cached or not cached.get('products'):
            return True
        age_hours = self._cache_age_hours(cache_key)
        return age_hours is None or age_hours > max_age_hours

    @staticmethod
    def _with_data_status(result: Dict, status: str, refresh_error: Optional[str] = None) -> Dict:
        """Annotate source results so cached or sample evidence cannot appear live."""
        tagged = dict(result or {})
        tagged["data_status"] = status
        tagged["captured_at"] = tagged.get("timestamp")
        if refresh_error:
            tagged["refresh_error"] = str(refresh_error)[:200]
        else:
            tagged.pop("refresh_error", None)
        return tagged

    def _fresh_cached_result(self, cache_key: str) -> Optional[Dict]:
        cached = self.cache.get(cache_key)
        if cached and cached.get("products") and not self._should_scrape(cache_key):
            return self._with_data_status(cached, "cached_fresh")
        return None

    def _stale_cache_or_unavailable(self, cache_key: str, empty_result: Dict, error: str) -> Dict:
        """Prefer disclosed stale evidence over pretending refresh succeeded."""
        cached = self.cache.get(cache_key)
        age_hours = self._cache_age_hours(cache_key)
        if (
            cached
            and cached.get("products")
            and age_hours is not None
            and age_hours <= self.STALE_CACHE_MAX_AGE_HOURS
        ):
            return self._with_data_status(cached, "cached_stale", error)
        unavailable = dict(empty_result)
        unavailable["refresh_error"] = str(error)[:200]
        unavailable["data_status"] = "unavailable"
        return unavailable

    def _store_live_result(self, cache_key: str, result: Dict) -> Dict:
        lock = getattr(self, "_cache_lock", None)
        if lock:
            with lock:
                self.cache[cache_key] = result
                self._save_cache()
        else:
            self.cache[cache_key] = result
            self._save_cache()
        return self._with_data_status(result, "live")
    
    
    # ═══════════════════════════════════════════════════════════
    #  SHOPIFY API SCRAPERS (Campmor + Swanson)
    # ═══════════════════════════════════════════════════════════
    
    @staticmethod
    def _lowest_priced_variant(product: Dict) -> Optional[tuple[float, Optional[float], Dict]]:
        """Use one Shopify variant for both sale and comparison prices."""
        priced_variants = []
        for variant in product.get("variants", []):
            try:
                price = float(variant.get("price"))
            except (TypeError, ValueError):
                continue
            compare_at = None
            try:
                if variant.get("compare_at_price") not in (None, ""):
                    compare_at = float(variant.get("compare_at_price"))
            except (TypeError, ValueError):
                compare_at = None
            priced_variants.append((price, compare_at, variant))
        return min(priced_variants, key=lambda item: item[0]) if priced_variants else None

    @staticmethod
    def _is_relevant_product(product: Dict, category: str) -> bool:
        """Reject obvious catalog spillover from retailer collection pages."""
        if category != "clothing":
            return True
        product_text = f"{product.get('name', '')} {product.get('product_type', '')}".lower()
        excluded_items = (
            "bottle", "flask", "gift card", "voucher", "decal", "sticker",
            "watch", "charging dock", "lunch box", "towel",
        )
        return not any(item in product_text for item in excluded_items)

    @classmethod
    def _clean_products(cls, products: List[Dict], category: str) -> List[Dict]:
        """Keep relevant products and the lowest displayed offer per product name."""
        cleaned = []
        index_by_name = {}
        for product in products:
            if not cls._is_relevant_product(product, category):
                continue
            name_key = str(product.get("name", "")).strip().lower()
            if not name_key:
                continue
            if name_key in index_by_name:
                existing_index = index_by_name[name_key]
                try:
                    existing_price = float(str(cleaned[existing_index].get("price", "")).replace("$", "").replace(",", ""))
                    new_price = float(str(product.get("price", "")).replace("$", "").replace(",", ""))
                except ValueError:
                    continue
                if new_price < existing_price:
                    cleaned[existing_index] = product
                continue
            index_by_name[name_key] = len(cleaned)
            cleaned.append(product)
        return cleaned

    def _scrape_shopify_collection(self, domain: str, collection_handle: str,
                                   site_name: str, category: str, max_pages: int = 3) -> Dict:
        """
        Universal Shopify scraper - works for ANY Shopify store
        Uses public Shopify Storefront API (no authentication needed)
        
        Args:
            domain: Site domain (e.g., "www.campmor.com")
            collection_handle: Shopify collection slug (e.g., "sleeping-bags")
            site_name: Display name for competitor
            category: Product category
            max_pages: Max pages to scrape (default 3 = 750 products max)
        """
        cache_key = f"{site_name.lower()}_{category}_{collection_handle}"
        
        cached = self._fresh_cached_result(cache_key)
        if cached:
            cached["products"] = self._clean_products(cached.get("products", []), category)
            if cached["products"]:
                logger.info(f"Using cached {site_name} data")
                return cached
        
        logger.info(f"🛒 Scraping {site_name} via Shopify API...")
        
        all_products = []
        page = 1
        
        try:
            while page <= max_pages:
                url = f"https://{domain}/collections/{collection_handle}/products.json"
                params = {"limit": 250, "page": page}
                
                logger.info(f"  Fetching page {page}...")
                response = self.client.get(
                    url,
                    params=params,
                    timeout=15,
                    headers={"Accept": "application/json", "Accept-Encoding": "gzip, deflate"}
                )

                if response.status_code != 200:
                    logger.warning(f"  Stopped at page {page}: HTTP {response.status_code} — {response.text[:200]}")
                    break

                # ✅ FIX: Handle gzip/encoding issues
                try:
                    data = response.json()
                except Exception:
                    # Try manual decoding if response.json() fails
                    import gzip
                    try:
                        raw_bytes = response.content
                        decompressed = gzip.decompress(raw_bytes)
                        data = json.loads(decompressed.decode('utf-8'))
                        logger.info(f"  ✅ Decoded gzip response successfully")
                    except Exception:
                        # Last resort: decode with error handling
                        try:
                            raw_text = response.content.decode('utf-8', errors='ignore')
                            data = json.loads(raw_text)
                            logger.info(f"  ✅ Decoded with error-ignore mode")
                        except Exception as e:
                            logger.error(f"  ❌ Cannot decode response: {e}")
                            break

                products = data.get("products", [])
                
                if not products:
                    logger.info(f"  No more products at page {page}")
                    break
                
                for p in products:
                    selected_variant = self._lowest_priced_variant(p)
                    if not selected_variant:
                        continue
                    min_price, compare_at, variant = selected_variant
                    
                    all_products.append({
                        'name': p.get("title", "Unknown"),
                        'price': f"${min_price:.2f}",
                        'compare_at_price': f"${compare_at:.2f}" if compare_at else None,
                        'brand': p.get("vendor", site_name),
                        'sku': variant.get("sku", ""),
                        'product_type': p.get("product_type", category),
                        'url': f"https://{domain}/products/{p.get('handle', '')}",
                        'image': p.get("images", [{}])[0].get("src", "") if p.get("images") else "",
                        'source': site_name
                    })
                
                logger.info(f"  Page {page}: {len(products)} products | Total: {len(all_products)}")
                page += 1
                time.sleep(0.5)  # Be polite
            
            all_products = self._clean_products(all_products, category)

            if not all_products:
                return self._stale_cache_or_unavailable(
                    cache_key,
                    {
                        'competitor': site_name,
                        'category': category,
                        'products': [],
                        'method': 'Shopify API (failed)'
                    },
                    "Live refresh returned no products",
                )

            result = {
                'competitor': site_name,
                'category': category,
                'products': all_products[:20],  # Limit to 20 for demo
                'total_found': len(all_products),
                'timestamp': datetime.now().isoformat(),
                'method': 'Shopify API',
                'url': f"https://{domain}/collections/{collection_handle}"
            }
            
            logger.info(f"✅ {site_name}: {len(all_products)} total products (showing 20)")
            return self._store_live_result(cache_key, result)
            
        except Exception as e:
            logger.error(f"{site_name} Shopify scrape failed: {e}")
            return self._stale_cache_or_unavailable(
                cache_key,
                {
                    'competitor': site_name,
                    'category': category,
                    'products': [],
                    'error': str(e),
                    'method': 'Shopify API (failed)'
                },
                str(e),
            )
    
    def _scrape_campmor(self, category: str = "sports") -> Dict:
        """Scrape Campmor (Shopify store) using requests library"""
        cache_key = f"campmor_{category}"
        
        cached = self._fresh_cached_result(cache_key)
        if cached:
            logger.info(f"Using cached Campmor data")
            return cached
        
        logger.info("🛒 Scraping Campmor via Shopify API (requests)...")
        
        collection_map = {
            'sports': 'sleeping-bags',
            'electronics': 'electronics',
            'home': 'camp-furniture',
            'clothing': 'mens-outdoor-clothing',
            'food': 'camping-food'
        }
        
        collection = collection_map.get(category, 'sleeping-bags')
        all_products = []
        
        try:
            import requests as req
            
            for page in range(1, 4):  # Max 3 pages
                url = f"https://www.campmor.com/collections/{collection}/products.json"
                
                logger.info(f"  Fetching page {page}...")
                resp = req.get(
                    url,
                    params={"limit": 250, "page": page},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "Accept": "application/json"
                    },
                    timeout=15
                )
                
                logger.info(f"  Status: {resp.status_code}, Content-Type: {resp.headers.get('content-type')}")
                logger.info(f"  Response size: {len(resp.content)} bytes")
                
                if resp.status_code != 200:
                    logger.warning(f"  HTTP {resp.status_code}")
                    break
                
                data = resp.json()  # requests handles encoding automatically
                products = data.get("products", [])
                
                if not products:
                    logger.info(f"  No more products at page {page}")
                    break
                
                for p in products:
                    selected_variant = self._lowest_priced_variant(p)
                    if not selected_variant:
                        continue
                    min_price, compare_at, variant = selected_variant
                    
                    all_products.append({
                        'name': p.get("title", "Unknown"),
                        'price': f"${min_price:.2f}",
                        'compare_at_price': f"${compare_at:.2f}" if compare_at else None,
                        'brand': p.get("vendor", "Campmor"),
                        'sku': variant.get("sku", ""),
                        'product_type': p.get("product_type", category),
                        'source': 'Campmor'
                    })
                
                logger.info(f"  Page {page}: {len(products)} products | Total: {len(all_products)}")
                time.sleep(0.5)
            
            if not all_products:
                return self._stale_cache_or_unavailable(
                    cache_key,
                    {
                        'competitor': 'Campmor',
                        'category': category,
                        'products': [],
                        'method': 'Shopify API (requests, failed)'
                    },
                    "Live refresh returned no products",
                )

            result = {
                'competitor': 'Campmor',
                'category': category,
                'products': all_products[:20],
                'total_found': len(all_products),
                'timestamp': datetime.now().isoformat(),
                'method': 'Shopify API (requests)',
                'url': f"https://www.campmor.com/collections/{collection}"
            }
            
            logger.info(f"✅ Campmor: {len(all_products)} total products (showing 20)")
            return self._store_live_result(cache_key, result)
            
        except Exception as e:
            logger.error(f"Campmor scrape failed: {e}")
            import traceback
            logger.error(traceback.format_exc()[:500])
            return self._stale_cache_or_unavailable(
                cache_key,
                {
                    'competitor': 'Campmor',
                    'category': category,
                    'products': [],
                    'error': str(e),
                    'method': 'Shopify API (failed)'
                },
                str(e),
            )
    
    def _scrape_swanson(self, category: str = "food") -> Dict:
        """Scrape Swanson Vitamins (Shopify store) - Supplements/Health"""
        
        # Map categories to Shopify collection handles
        collection_map = {
            'food': 'vitamins-and-supplements-8',
            'sports': 'protein-63',
            'electronics': 'fitness-trackers',
            'home': 'essential-oils',
            'clothing': 'yoga-wear'
        }
        
        collection = collection_map.get(category, 'vitamins-and-supplements-8')
        
        return self._scrape_shopify_collection(
            domain="www.swansonvitamins.com",
            collection_handle=collection,
            site_name="Swanson Vitamins",
            category=category
        )
    
    
    # ═══════════════════════════════════════════════════════════
    #  BEAUTIFULSOUP SCRAPERS (Static HTML)
    # ═══════════════════════════════════════════════════════════
    
    def _scrape_newegg(self, category: str = "electronics") -> Dict:
        """Scrape Newegg (BeautifulSoup) - Electronics"""
        cache_key = f"newegg_{category}"
        
        cached = self._fresh_cached_result(cache_key)
        if cached:
            logger.info(f"Using cached Newegg data")
            return cached
        
        logger.info("🌐 Scraping Newegg (BeautifulSoup)...")
        
        try:
            search_terms = {
                'electronics': 'laptop',
                'home': 'smart+home',
                'clothing': 'gaming+chair',
                'food': 'coffee+maker',
                'sports': 'fitness+tracker'
            }
            
            term = search_terms.get(category, 'laptop')
            url = f"https://www.newegg.com/p/pl?d={term}&N=4131"
            
            response = self.client.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            products = []
            for item in soup.select('.item-cell')[:10]:
                name_elem = item.select_one('.item-title')
                price_elem = item.select_one('.price-current strong')
                
                if name_elem and price_elem:
                    products.append({
                        'name': name_elem.get_text(strip=True),
                        'price': f"${price_elem.get_text(strip=True)}",
                        'source': 'Newegg'
                    })
            
            if not products:
                return self._stale_cache_or_unavailable(
                    cache_key,
                    {
                        'competitor': 'Newegg',
                        'category': category,
                        'products': [],
                        'method': 'BeautifulSoup (failed)'
                    },
                    "Live refresh returned no products",
                )

            data = {
                'competitor': 'Newegg',
                'category': category,
                'products': products,
                'timestamp': datetime.now().isoformat(),
                'url': url,
                'method': 'BeautifulSoup'
            }
            
            logger.info(f"✅ Newegg {category}: {len(products)} products (BeautifulSoup)")
            return self._store_live_result(cache_key, data)
            
        except Exception as e:
            logger.error(f"Newegg scrape failed: {e}")
            return self._stale_cache_or_unavailable(
                cache_key,
                {
                    'competitor': 'Newegg',
                    'category': category,
                    'products': [],
                    'error': str(e),
                    'method': 'BeautifulSoup (failed)'
                },
                str(e),
            )
    
    
    # ═══════════════════════════════════════════════════════════
    #  IKEA API SCRAPER (cloud-native, no browser required)
    # ═══════════════════════════════════════════════════════════

    def _scrape_ikea_api(self, category: str = "home") -> Dict:
        """Scrape IKEA via internal JSON API — no browser needed, cloud-safe."""
        cache_key = f"ikea_{category}"

        cached = self._fresh_cached_result(cache_key)
        if cached:
            return cached

        logger.info("🌐 Scraping IKEA (internal API)...")

        search_terms = {
            'electronics': 'wireless charger',
            'home': 'bookcase',
            'clothing': 'curtains',
            'food': 'kitchen storage',
            'sports': 'outdoor furniture',
        }
        query = search_terms.get(category, 'bookcase')

        try:
            url = "https://sik.search.blue.cdtapps.com/us/en/search-result-page"
            params = {"q": query, "size": 10, "c": "listaf", "v": "20"}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://www.ikea.com/",
            }

            resp = httpx.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            items = (
                data.get("searchResultPage", {})
                    .get("products", {})
                    .get("main", {})
                    .get("items", [])
            )

            products = []
            for item in items[:10]:
                product = item.get("product", {})
                name = product.get("name", "") or product.get("typeName", "")
                price_obj = product.get("salesPrice", {}) or product.get("price", {})
                price = price_obj.get("numeral", "") or price_obj.get("current", {}).get("numeral", "")
                if name:
                    products.append({
                        "name": name,
                        "price": f"${price}" if price else "N/A",
                        "source": "IKEA",
                    })

            if not products:
                return self._stale_cache_or_unavailable(
                    cache_key,
                    {
                        "competitor": "IKEA",
                        "category": category,
                        "products": [],
                        "method": "IKEA Search API (failed)",
                    },
                    "Live refresh returned no products",
                )

            result = {
                "competitor": "IKEA",
                "category": category,
                "products": products,
                "timestamp": datetime.now().isoformat(),
                "method": "IKEA Search API",
            }

            logger.info(f"✅ IKEA {category}: {len(products)} products (API)")
            return self._store_live_result(cache_key, result)

        except Exception as e:
            logger.warning(f"IKEA API failed ({e}), returning cached/empty")
            return self._stale_cache_or_unavailable(
                cache_key,
                {
                    "competitor": "IKEA",
                    "category": category,
                    "products": [],
                    "error": str(e),
                    "method": "IKEA Search API (failed)",
                },
                str(e),
            )
    
    

    # ═══════════════════════════════════════════════════════════
    #  NEW COMPETITORS
    # ═══════════════════════════════════════════════════════════

    def _scrape_goalzero(self, category: str = "electronics") -> Dict:
        """Scrape Goal Zero (Shopify) - Portable Power / Electronics"""
        collection_map = {
            'electronics': 'portable-power',
            'sports': 'solar-panels',
            'home': 'home-integration',
        }
        return self._scrape_shopify_collection(
            domain="www.goalzero.com",
            collection_handle=collection_map.get(category, 'power-stations'),
            site_name="Goal Zero",
            category=category
        )

    def _scrape_nativepath(self, category: str = "food") -> Dict:
        """Scrape NativePath (Shopify) - Supplements / Health Food"""
        return self._scrape_shopify_collection(
            domain="www.nativepath.com",
            collection_handle="all",
            site_name="NativePath",
            category=category
        )

    def _scrape_taylorstitch(self, category: str = "clothing") -> Dict:
        """Scrape Taylor Stitch (Shopify) - Men's Premium Clothing"""
        return self._scrape_shopify_collection(
            domain="www.taylorstitch.com",
            collection_handle="mens-shirts-sweaters",
            site_name="Taylor Stitch",
            category=category
        )

    def _scrape_chubbies(self, category: str = "clothing") -> Dict:
        """Scrape Chubbies (Shopify) - Men's Casual Clothing"""
        return self._scrape_shopify_collection(
            domain="www.chubbies.com",
            collection_handle="all-tops",
            site_name="Chubbies",
            category=category
        )

    def _scrape_finisterre(self, category: str = "clothing") -> Dict:
        """Scrape Finisterre (Shopify) - Sustainable Outdoor Clothing"""
        return self._scrape_shopify_collection(
            domain="www.finisterre.com",
            collection_handle="mens-clothing",
            site_name="Finisterre",
            category=category
        )

    # ═══════════════════════════════════════════════════════════
    #  MOCK DATA FALLBACK
    # ═══════════════════════════════════════════════════════════
    
    def _get_mock_data(self, category: str) -> Dict:
        """Fallback mock data if all scrapers fail"""
        
        mock_data = {
            "electronics": {
                "competitor": "Mock Electronics Retailer",
                "products": [
                    {"name": "Gaming Laptop 15-inch RTX 4060", "price": "$899", "source": "Mock"},
                    {"name": "Wireless Noise-Cancelling Headphones", "price": "$149", "source": "Mock"},
                    {"name": "4K Smart TV 55-inch", "price": "$599", "source": "Mock"},
                    {"name": "Mechanical Gaming Keyboard RGB", "price": "$89", "source": "Mock"},
                    {"name": "Portable SSD 1TB", "price": "$109", "source": "Mock"}
                ]
            },
            "home": {
                "competitor": "Mock Home Goods Retailer",
                "products": [
                    {"name": "Smart Coffee Maker WiFi", "price": "$79", "source": "Mock"},
                    {"name": "Memory Foam Mattress Queen", "price": "$399", "source": "Mock"},
                    {"name": "Robot Vacuum Cleaner", "price": "$249", "source": "Mock"},
                    {"name": "Air Purifier HEPA", "price": "$129", "source": "Mock"},
                    {"name": "LED Desk Lamp Dimmable", "price": "$35", "source": "Mock"}
                ]
            },
            "clothing": {
                "competitor": "Mock Clothing Retailer",
                "products": [
                    {"name": "Men's Winter Parka Jacket", "price": "$89", "source": "Mock"},
                    {"name": "Women's Running Shoes", "price": "$65", "source": "Mock"},
                    {"name": "Unisex Hoodie Premium Cotton", "price": "$45", "source": "Mock"},
                    {"name": "Jeans Slim Fit Stretch", "price": "$39", "source": "Mock"},
                    {"name": "Athletic Leggings High-Waist", "price": "$29", "source": "Mock"}
                ]
            },
            "food": {
                "competitor": "Mock Health Food Retailer",
                "products": [
                    {"name": "Organic Protein Powder 2lb Vanilla", "price": "$29", "source": "Mock"},
                    {"name": "Multivitamin Gummies 120ct", "price": "$19", "source": "Mock"},
                    {"name": "Omega-3 Fish Oil 180 Softgels", "price": "$24", "source": "Mock"},
                    {"name": "Organic Green Tea 100 Bags", "price": "$12", "source": "Mock"},
                    {"name": "Probiotic 30 Billion CFU", "price": "$32", "source": "Mock"}
                ]
            },
            "sports": {
                "competitor": "Mock Sports Retailer",
                "products": [
                    {"name": "Camping Tent 4-Person Waterproof", "price": "$149", "source": "Mock"},
                    {"name": "Yoga Mat Premium 6mm", "price": "$35", "source": "Mock"},
                    {"name": "Hiking Backpack 40L", "price": "$89", "source": "Mock"},
                    {"name": "Resistance Bands Set of 5", "price": "$25", "source": "Mock"},
                    {"name": "Water Bottle Insulated 32oz", "price": "$28", "source": "Mock"}
                ]
            }
        }
        
        return {
            'competitor': mock_data[category]['competitor'],
            'category': category,
            'products': mock_data[category]['products'],
            'timestamp': datetime.now().isoformat(),
            'method': 'Mock Data (Fallback)'
        }
    
    
    # ═══════════════════════════════════════════════════════════
    #  ASYNC PARALLEL SCRAPING
    # ═══════════════════════════════════════════════════════════
    
    async def scrape_competitor_pricing_async(
        self, category: str, competitor: Optional[str] = None
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Scrape multiple competitors for a category
        Independent retailer requests run concurrently; each scraper preserves its own pacing.
        """
        
        scope = f" for {competitor}" if competitor else ""
        logger.info(f"🚀 Scraping competitors for category: {category}{scope}")
        start = time.time()
        
        results = []
        scraper_statuses = []  # Track per-scraper status for UI dashboard
        
        # Define scraper methods per category
        scraper_methods = {
            'electronics': [self._scrape_newegg, self._scrape_goalzero],
            'home': [self._scrape_ikea_api],
            'clothing': [self._scrape_taylorstitch, self._scrape_chubbies, self._scrape_finisterre],
            'food': [self._scrape_swanson, self._scrape_nativepath],
            'sports': [self._scrape_campmor]
        }
        
        methods = scraper_methods.get(category, [])
        if competitor:
            target_method = self.COMPETITOR_SCRAPER_METHODS.get(competitor.lower())
            if target_method:
                methods = [getattr(self, target_method)]
            else:
                methods = []
                scraper_statuses.append({
                    'name': competitor,
                    'status': 'unsupported',
                    'products': 0,
                    'time': 0,
                    'error': 'Competitor is not configured for live scraping'
                })
        
        async def run_method(method):
            scraper_start = time.time()
            try:
                logger.info(f"🔄 Running {method.__name__}...")
                result = await asyncio.to_thread(method, category)
                elapsed_s = round(time.time() - scraper_start, 2)
                if result and result.get('products'):
                    logger.info(f"✅ {method.__name__}: {len(result['products'])} products")
                    status = {
                        'name': result.get('competitor', method.__name__),
                        'status': result.get('data_status', 'live'),
                        'products': len(result['products']),
                        'time': elapsed_s,
                        'error': result.get('refresh_error'),
                        'captured_at': result.get('captured_at') or result.get('timestamp'),
                    }
                    return result, status
                logger.warning(f"⚠️  {method.__name__}: No products found")
                status = {
                    'name': result.get('competitor', method.__name__) if result else method.__name__,
                    'status': result.get('data_status', 'empty') if result else 'empty',
                    'products': 0,
                    'time': elapsed_s,
                    'error': result.get('refresh_error', 'No products returned') if result else 'No products returned',
                }
                return None, status
            except Exception as e:
                elapsed_s = round(time.time() - scraper_start, 2)
                logger.error(f"❌ {method.__name__} failed: {str(e)[:200]}")
                return None, {
                    'name': method.__name__,
                    'status': 'failed',
                    'products': 0,
                    'time': elapsed_s,
                    'error': str(e)[:150]
                }

        for result, status in await asyncio.gather(*(run_method(method) for method in methods)):
            if result:
                results.append(result)
            scraper_statuses.append(status)
        
        # Filter empty results
        results = [r for r in results if r and 'products' in r and r['products']]
        
        # A named competitor must never be represented by generic category samples.
        if not results and competitor:
            logger.warning(f"No live products available for named competitor: {competitor}")
        elif not results and settings.web_allow_sample_fallback:
            logger.warning(f"All scrapers failed for {category}, using explicitly enabled sample data")
            mock = self._get_mock_data(category)
            mock['is_mock'] = True
            mock = self._with_data_status(mock, "sample")
            results.append(mock)
            scraper_statuses.append({
                'name': 'Mock Data Fallback',
                'status': 'sample',
                'products': len(mock.get('products', [])),
                'time': 0,
                'error': 'All live scrapers failed - using enabled sample data',
                'captured_at': mock.get('captured_at'),
            })
        elif not results:
            logger.warning(f"All live scrapers failed for {category}; sample fallback is disabled")
        
        elapsed = time.time() - start
        logger.info(f"✅ Scraped {len(results)} sources for {category} in {elapsed:.2f}s")
        
        return results, scraper_statuses

    
    def scrape_competitor_pricing(
        self, category: str, competitor: Optional[str] = None
    ) -> Dict:
        """
        Synchronous wrapper for async scraping
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        results, scraper_statuses = loop.run_until_complete(
            self.scrape_competitor_pricing_async(category, competitor=competitor)
        )
        
        return {
            'category': category,
            'competitors': results,
            'scraper_statuses': scraper_statuses,
            'timestamp': datetime.now().isoformat()
        }
    
    
    # ═══════════════════════════════════════════════════════════
    #  MAIN QUERY METHOD
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _compact_pricing_context(pricing_data: Dict) -> Dict:
        """Keep pricing evidence in model context without scraper-only fields."""
        competitors = []
        for competitor in pricing_data.get("competitors", []):
            products = []
            for product in competitor.get("products", []):
                compact_product = {
                    key: product[key]
                    for key in ("name", "price", "compare_at_price", "source")
                    if product.get(key) not in (None, "")
                }
                if compact_product:
                    products.append(compact_product)
            competitors.append({
                "competitor": competitor.get("competitor", "Unknown"),
                "products": products,
                "is_mock": bool(competitor.get("is_mock")),
                "data_status": competitor.get("data_status", "unknown"),
                "captured_at": competitor.get("captured_at") or competitor.get("timestamp"),
                "refresh_error": competitor.get("refresh_error"),
            })
        return {
            "category": pricing_data.get("category"),
            "competitors": competitors,
        }

    def _build_answer_prompt(self, question: str, pricing_data: Dict) -> str:
        """Build the model prompt from evidence needed for price comparisons."""
        compact_context = self._compact_pricing_context(pricing_data)
        return f"""Based on competitor pricing data, answer this question:

QUESTION: {question}

COMPETITOR DATA:
{json.dumps(compact_context, indent=2)}

Answer concisely using only the supplied competitor data. Include price ranges and sources.
If the question names one competitor, do not mention competitors not present in the data.
If any competitor has is_mock=true, explicitly state that its data is sample fallback data, not live pricing.
If any competitor has data_status="cached_stale", explicitly state that live refresh failed and give its captured_at time.
Format as bullet points with competitor names."""

    @staticmethod
    def _price_amount(value) -> Optional[Decimal]:
        """Parse a product price into a stable decimal amount."""
        if value in (None, ""):
            return None
        if isinstance(value, (int, float, Decimal)):
            try:
                return Decimal(str(value))
            except InvalidOperation:
                return None
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value))
        if not match:
            return None
        try:
            return Decimal(match.group(0).replace(",", ""))
        except InvalidOperation:
            return None

    @staticmethod
    def _format_price(amount: Decimal) -> str:
        return f"${amount:,.2f}"

    @classmethod
    def _priced_products(cls, pricing_data: Dict) -> List[Dict]:
        priced = []
        for source in pricing_data.get("competitors", []):
            source_name = source.get("competitor", "Unknown")
            for product in source.get("products", []):
                amount = cls._price_amount(product.get("price"))
                if amount is not None:
                    priced.append({
                        "competitor": source_name,
                        "product": product,
                        "price": amount,
                    })
        return priced

    @staticmethod
    def _data_quality_note(pricing_data: Dict) -> str:
        notes = []
        if any(source.get("is_mock") for source in pricing_data.get("competitors", [])):
            notes.append("Sample fallback data shown because live scraping was unavailable.")
        stale_sources = [
            source for source in pricing_data.get("competitors", [])
            if source.get("data_status") == "cached_stale"
        ]
        for source in stale_sources:
            captured_at = source.get("captured_at") or source.get("timestamp") or "an earlier capture"
            notes.append(
                f"{source.get('competitor', 'Source')} prices are cached from {captured_at}; live refresh failed."
            )
        return "\n\n" + "\n".join(f"*{note}*" for note in notes) if notes else ""

    @classmethod
    def _deterministic_answer(
        cls, question: str, pricing_data: Dict, competitor: Optional[str] = None
    ) -> Optional[str]:
        """Answer exact pricing operations without paying for model generation."""
        q = str(question or "").lower()
        priced = cls._priced_products(pricing_data)
        note = cls._data_quality_note(pricing_data)

        if not priced:
            if competitor:
                return f"No live pricing data is currently available for **{competitor}**."
            return "No competitor pricing data is currently available."

        interpretation_terms = (
            "strategy",
            "positioning",
            "suggest",
            "recommend",
            "why",
            "insight",
            "implication",
            "opportunit",
            "should we",
            "market trend",
        )
        if any(term in q for term in interpretation_terms):
            return None

        if any(term in q for term in ("discount", "on sale", "sale price", "original price")):
            discounted = []
            for item in priced:
                original = cls._price_amount(item["product"].get("compare_at_price"))
                if original is None or original <= item["price"]:
                    continue
                savings_pct = ((original - item["price"]) / original * Decimal("100")).quantize(Decimal("0.1"))
                discounted.append(
                    f"- **{item['competitor']}** - {item['product'].get('name', 'Product')}: "
                    f"{cls._format_price(item['price'])} "
                    f"(originally {cls._format_price(original)}, {savings_pct}% off)"
                )
            if discounted:
                return "**Discounted products**\n" + "\n".join(discounted) + note
            return "No discounted products with an original price were found in the available data." + note

        threshold_match = re.search(
            r"\b(under|below|less than|up to|over|above|more than|at least)\s+\$?\s*([\d,]+(?:\.\d+)?)",
            q,
        )
        if threshold_match:
            operator, raw_threshold = threshold_match.groups()
            threshold = Decimal(raw_threshold.replace(",", ""))
            comparisons = {
                "under": lambda value: value < threshold,
                "below": lambda value: value < threshold,
                "less than": lambda value: value < threshold,
                "up to": lambda value: value <= threshold,
                "over": lambda value: value > threshold,
                "above": lambda value: value > threshold,
                "more than": lambda value: value > threshold,
                "at least": lambda value: value >= threshold,
            }
            matches = [item for item in priced if comparisons[operator](item["price"])]
            if not matches:
                return f"No products were found {operator} {cls._format_price(threshold)}." + note
            lines = [
                f"- **{item['competitor']}** - {item['product'].get('name', 'Product')}: {cls._format_price(item['price'])}"
                for item in sorted(matches, key=lambda item: item["price"])
            ]
            return (
                f"**Products {operator} {cls._format_price(threshold)}**\n"
                + "\n".join(lines)
                + note
            )

        if re.search(r"\b(how many|number of|count)\b", q) and "product" in q:
            grouped = {}
            for item in priced:
                grouped[item["competitor"]] = grouped.get(item["competitor"], 0) + 1
            lines = [f"- **{name}**: {count} products" for name, count in grouped.items()]
            return f"**Products found:** {len(priced)} total\n" + "\n".join(lines) + note

        if any(term in q for term in ("cheapest", "lowest price", "lowest-priced", "least expensive")):
            lowest = min(item["price"] for item in priced)
            matches = [item for item in priced if item["price"] == lowest]
            lines = [
                f"- **{item['competitor']}** - {item['product'].get('name', 'Product')}: {cls._format_price(lowest)}"
                for item in matches
            ]
            return "**Cheapest product found**\n" + "\n".join(lines) + note

        if any(term in q for term in ("most expensive", "highest price", "highest-priced")):
            highest = max(item["price"] for item in priced)
            matches = [item for item in priced if item["price"] == highest]
            lines = [
                f"- **{item['competitor']}** - {item['product'].get('name', 'Product')}: {cls._format_price(highest)}"
                for item in matches
            ]
            return "**Most expensive product found**\n" + "\n".join(lines) + note

        if "price range" in q or "range of prices" in q:
            grouped = {}
            for item in priced:
                grouped.setdefault(item["competitor"], []).append(item["price"])
            lines = [
                f"- **{name}**: {cls._format_price(min(amounts))} - {cls._format_price(max(amounts))} "
                f"({len(amounts)} products)"
                for name, amounts in grouped.items()
            ]
            if len(grouped) > 1:
                lines.append(
                    f"- **Overall**: {cls._format_price(min(item['price'] for item in priced))} - "
                    f"{cls._format_price(max(item['price'] for item in priced))}"
                )
            return "**Price range**\n" + "\n".join(lines) + note

        requests_product_list = (
            "product" in q
            and any(term in q for term in ("price", "prices", "available"))
            and not any(term in q for term in ("compare", "strategy", "suggest", "recommend", "why"))
        )
        if requests_product_list:
            lines = []
            for item in sorted(priced, key=lambda product: (product["competitor"], product["price"])):
                lines.append(
                    f"- **{item['competitor']}** - {item['product'].get('name', 'Product')}: "
                    f"{cls._format_price(item['price'])}"
                )
            return "**Products and prices**\n" + "\n".join(lines) + note

        return None
    
    def query(
        self, question: str, category: str = None, competitor: Optional[str] = None
    ) -> Dict:
        """
        Main Web Agent query method
        """
        
        logger.info(f"\n{'='*50}")
        logger.info(f"🌐 WEB AGENT: {question}")
        logger.info(f"{'='*50}")
        
        start_time = time.time()
        
        if category:
            # Category-specific pricing
            pricing_data = self.scrape_competitor_pricing(category, competitor=competitor)
            deterministic_answer = self._deterministic_answer(question, pricing_data, competitor=competitor)
            if deterministic_answer is not None:
                elapsed = time.time() - start_time
                logger.info(f"Web query answered deterministically in {elapsed:.2f}s")
                return {
                    'answer': deterministic_answer,
                    'answer_mode': 'deterministic',
                    'model_used': 'Deterministic calculation',
                    'raw_data': pricing_data,
                    'category': category,
                    'query_time': round(elapsed, 2)
                }
            
            # Use LLM to answer based on scraped data
            prompt = self._build_answer_prompt(question, pricing_data)

            try:
                if self.groq_client:
                    result = self.llm_gateway.invoke_with_fallback(
                        prompt=prompt,
                        models=[{
                            "name": settings.groq_model,
                            "type": "groq",
                            "description": "Groq Llama 3.3 70B",
                        }],
                        tracker=quota_tracker,
                        task="web.answer",
                        temperature=0.1,
                        metadata={"agent": "web", "category": category, "competitor": competitor},
                        response_validator=lambda content: bool(content.strip()),
                    )
                    if not result.get("success"):
                        raise RuntimeError(result.get("error", "Web answer LLM failed"))
                    answer = result["response"] + self._data_quality_note(pricing_data)
                else:
                    answer = (
                        "Groq unavailable. Raw data:\n"
                        + json.dumps(pricing_data, indent=2)
                        + self._data_quality_note(pricing_data)
                    )
                    
                elapsed = time.time() - start_time
                
                logger.info(f"✅ Web query complete in {elapsed:.2f}s")
                
                return {
                    'answer': answer,
                    'answer_mode': 'llm' if self.groq_client else 'raw_data',
                    'model_used': result.get('model_used') if self.groq_client else 'Raw scraped data',
                    'raw_data': pricing_data,
                    'category': category,
                    'query_time': round(elapsed, 2)
                }
                
            except Exception as e:
                quota_tracker.report_failure("llama-3.3-70b-versatile", str(e))
                logger.warning(f"LLM failed for web answer, using raw data fallback: {e}")
                competitors = pricing_data.get('competitors', [])
                fallback_lines = []
                for comp in competitors:
                    name = comp.get('competitor', 'Unknown')
                    products = comp.get('products', [])
                    if products:
                        prices = [p.get('price', '') for p in products[:3]]
                        fallback_lines.append(f"- **{name}**: {', '.join(prices)}")
                fallback_answer = "\n".join(fallback_lines) if fallback_lines else "No competitor pricing data available."
                fallback_answer += self._data_quality_note(pricing_data)
                return {
                    'answer': fallback_answer,
                    'answer_mode': 'fallback',
                    'model_used': 'Raw scraped data fallback',
                    'raw_data': pricing_data,
                    'category': category,
                    'query_time': round(time.time() - start_time, 2),
                    'llm_error': str(e)
                }
        else:
            # General query - return generic market info
            answer = "Please specify a product category (electronics, home, clothing, food, or sports) for competitor pricing data."
            
            return {
                'answer': answer,
                'raw_data': {},
                'query_time': round(time.time() - start_time, 2)
            }
    
    def close(self):
        """Cleanup resources"""
        self.client.close()
        logger.info("🔌 Web Agent closed")


# ═══════════════════════════════════════════════════════════
#  SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════

_web_instance = None

def get_web_agent() -> WebAgent:
    """Get singleton Web Agent instance"""
    global _web_instance
    if _web_instance is None:
        _web_instance = WebAgent()
    return _web_instance


# ═══════════════════════════════════════════════════════════
#  CLI TESTING
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    """Test Web Agent from command line"""
    
    print("\n" + "="*70)
    print("🌐 WEB AGENT — Multi-Source Scraping Test")
    print("="*70 + "\n")
    
    agent = get_web_agent()
    
    # Test all 5 categories
    categories = ['electronics', 'home', 'clothing', 'food', 'sports']
    
    for cat in categories:
        print(f"\n{'─'*70}")
        print(f"📦 CATEGORY: {cat.upper()}")
        print('─'*70)
        
        result = agent.query(f"What are competitor prices for {cat}?", category=cat)
        
        # Truncate long answers
        answer = result.get('answer', 'No answer')
        if len(answer) > 500:
            answer = answer[:500] + "...[truncated]"
        
        print(f"\n📊 Answer:\n{answer}")
        print(f"\n⏱️  Time: {result['query_time']:.2f}s")
        
        if result.get('raw_data', {}).get('competitors'):
            print(f"\n📋 Scraped {len(result['raw_data']['competitors'])} competitor sources:")
            for comp in result['raw_data']['competitors']:
                method = comp.get('method', 'Unknown')
                products = len(comp.get('products', []))
                total = comp.get('total_found', products)
                print(f"  • {comp.get('competitor', 'Unknown')} ({method}): {products} products shown ({total} total)")
        
        print()
    
    agent.close()
    print("\n✅ Web Agent testing complete!\n")
