"""
Web Agent - Competitor Intelligence & Industry Data
Multi-source scraping: BeautifulSoup (static HTML) + Selenium (JS sites) + Shopify API

✅ 4 Production Scrapers:
   - Newegg (BeautifulSoup) - Electronics
   - IKEA (Selenium) - Home
   - Campmor (Shopify API) - Sports
   - Swanson (Shopify API) - Food/Supplements

✅ Features:
   - Smart caching (24-hour TTL)
   - Rate limiting
   - Mock data fallbacks
   - Async parallel execution
   - Multi-browser support (Firefox for stability)
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
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import requests as req_lib  # For Campmor (httpx has encoding issues)

# Selenium imports
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager

import sys
sys.path.append(str(Path(__file__).parent.parent))

from langchain_groq import ChatGroq
from config.settings import settings
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
    - Selenium (JavaScript-heavy sites)
    """
    
    # HTTP headers for BeautifulSoup requests
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    
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
        
        # Selenium driver (lazy initialization)
        self._driver = None
        
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
    
    def _should_scrape(self, cache_key: str, max_age_hours: int = 24) -> bool:
        """Check if cache is fresh enough AND has actual data"""
        cached = self.cache.get(cache_key)
        if not cached:
            return True
        # Always re-scrape if cached result has no products (failed earlier run)
        if not cached.get('products'):
            return True
        cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
        return (datetime.now() - cache_time).total_seconds() > max_age_hours * 3600
    
    def _get_selenium_driver(self):
        """
        Lazy initialize Firefox WebDriver
        Uses Firefox instead of Chrome (better stability on M4 Mac)
        """
        if self._driver is None:
            try:
                logger.info("🦊 Initializing Firefox WebDriver (NON-HEADLESS for anti-detection)...")
                
                firefox_options = FirefoxOptions()
                
                # ✅ REMOVE headless mode - real browser window prevents detection
                # firefox_options.add_argument('--headless')  # ← COMMENTED OUT
                
                # Anti-detection settings
                firefox_options.set_preference('dom.webdriver.enabled', False)
                firefox_options.set_preference('useAutomationExtension', False)
                firefox_options.set_preference('general.useragent.override', 
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0')
                
                service = FirefoxService(GeckoDriverManager().install())
                self._driver = webdriver.Firefox(service=service, options=firefox_options)
                
                logger.info("✅ Firefox WebDriver initialized (VISIBLE mode for human-like behavior)")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize Firefox: {e}")
                raise
        
        return self._driver
    
    
    # ═══════════════════════════════════════════════════════════
    #  SHOPIFY API SCRAPERS (Campmor + Swanson)
    # ═══════════════════════════════════════════════════════════
    
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
        cache_key = f"{site_name.lower()}_{category}"
        
        if not self._should_scrape(cache_key):
            logger.info(f"Using cached {site_name} data")
            return self.cache[cache_key]
        
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
                    # Get lowest variant price
                    variant_prices = [float(v.get("price", 0)) for v in p.get("variants", []) 
                                     if v.get("price")]
                    
                    if not variant_prices:
                        continue
                    
                    min_price = min(variant_prices)
                    
                    # Check for sale price
                    compare_prices = [float(v.get("compare_at_price", 0)) for v in p.get("variants", []) 
                                     if v.get("compare_at_price")]
                    compare_at = max(compare_prices) if compare_prices else None
                    
                    all_products.append({
                        'name': p.get("title", "Unknown"),
                        'price': f"${min_price:.2f}",
                        'compare_at_price': f"${compare_at:.2f}" if compare_at else None,
                        'brand': p.get("vendor", site_name),
                        'sku': p.get("variants", [{}])[0].get("sku", ""),
                        'product_type': p.get("product_type", category),
                        'url': f"https://{domain}/products/{p.get('handle', '')}",
                        'image': p.get("images", [{}])[0].get("src", "") if p.get("images") else "",
                        'source': site_name
                    })
                
                logger.info(f"  Page {page}: {len(products)} products | Total: {len(all_products)}")
                page += 1
                time.sleep(0.5)  # Be polite
            
            result = {
                'competitor': site_name,
                'category': category,
                'products': all_products[:20],  # Limit to 20 for demo
                'total_found': len(all_products),
                'timestamp': datetime.now().isoformat(),
                'method': 'Shopify API',
                'url': f"https://{domain}/collections/{collection_handle}"
            }
            
            self.cache[cache_key] = result
            self._save_cache()
            
            logger.info(f"✅ {site_name}: {len(all_products)} total products (showing 20)")
            return result
            
        except Exception as e:
            logger.error(f"{site_name} Shopify scrape failed: {e}")
            return self.cache.get(cache_key, {
                'competitor': site_name,
                'category': category,
                'products': [],
                'error': str(e),
                'method': 'Shopify API (failed)'
            })
    
    def _scrape_campmor(self, category: str = "sports") -> Dict:
        """Scrape Campmor (Shopify store) using requests library"""
        cache_key = f"campmor_{category}"
        
        if not self._should_scrape(cache_key):
            logger.info(f"Using cached Campmor data")
            return self.cache[cache_key]
        
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
                    variant_prices = [float(v.get("price", 0)) for v in p.get("variants", []) 
                                    if v.get("price")]
                    
                    if not variant_prices:
                        continue
                    
                    min_price = min(variant_prices)
                    
                    compare_prices = [float(v.get("compare_at_price", 0)) for v in p.get("variants", []) 
                                    if v.get("compare_at_price")]
                    compare_at = max(compare_prices) if compare_prices else None
                    
                    all_products.append({
                        'name': p.get("title", "Unknown"),
                        'price': f"${min_price:.2f}",
                        'compare_at_price': f"${compare_at:.2f}" if compare_at else None,
                        'brand': p.get("vendor", "Campmor"),
                        'sku': p.get("variants", [{}])[0].get("sku", ""),
                        'product_type': p.get("product_type", category),
                        'source': 'Campmor'
                    })
                
                logger.info(f"  Page {page}: {len(products)} products | Total: {len(all_products)}")
                time.sleep(0.5)
            
            result = {
                'competitor': 'Campmor',
                'category': category,
                'products': all_products[:20],
                'total_found': len(all_products),
                'timestamp': datetime.now().isoformat(),
                'method': 'Shopify API (requests)',
                'url': f"https://www.campmor.com/collections/{collection}"
            }
            
            self.cache[cache_key] = result
            self._save_cache()
            
            logger.info(f"✅ Campmor: {len(all_products)} total products (showing 20)")
            return result
            
        except Exception as e:
            logger.error(f"Campmor scrape failed: {e}")
            import traceback
            logger.error(traceback.format_exc()[:500])
            return {
                'competitor': 'Campmor',
                'category': category,
                'products': [],
                'error': str(e),
                'method': 'Shopify API (failed)'
            }
    
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
        
        if not self._should_scrape(cache_key):
            logger.info(f"Using cached Newegg data")
            return self.cache[cache_key]
        
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
            
            data = {
                'competitor': 'Newegg',
                'category': category,
                'products': products,
                'timestamp': datetime.now().isoformat(),
                'url': url,
                'method': 'BeautifulSoup'
            }
            
            self.cache[cache_key] = data
            self._save_cache()
            
            logger.info(f"✅ Newegg {category}: {len(products)} products (BeautifulSoup)")
            return data
            
        except Exception as e:
            logger.error(f"Newegg scrape failed: {e}")
            return self.cache.get(cache_key, {
                'competitor': 'Newegg',
                'category': category,
                'products': [],
                'error': str(e),
                'method': 'BeautifulSoup (failed)'
            })
    
    
    # ═══════════════════════════════════════════════════════════
    #  SELENIUM SCRAPERS (JavaScript Sites)
    # ═══════════════════════════════════════════════════════════
    
    def _scrape_ikea_selenium(self, category: str = "home") -> Dict:
        """Scrape IKEA (Selenium) - Home/Furniture"""
        cache_key = f"ikea_{category}"
        
        if not self._should_scrape(cache_key):
            return self.cache.get(cache_key, {})
        
        logger.info("🌐 Scraping IKEA (Selenium/Firefox)...")
        
        try:
            driver = self._get_selenium_driver()
            
            search_terms = {
                'electronics': 'wireless-charging',
                'home': 'bookcases-shelving-units',
                'clothing': 'textiles',
                'food': 'kitchen-dining',
                'sports': 'outdoor'
            }
            
            term = search_terms.get(category, 'bookcases-shelving-units')
            url = f"https://www.ikea.com/us/en/cat/{term}-st003/"
            
            logger.info(f"  Navigating to: {url}")
            driver.get(url)
            
            # Wait for product grid
            time.sleep(5)  # Let JavaScript render
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            products = []
            
            # Try multiple selectors (IKEA changes frequently)
            selectors = [
                '.plp-fragment-wrapper',
                '.plp-product-list__product',
                '[class*="product"]'
            ]
            
            items = []
            for selector in selectors:
                items = soup.select(selector)[:10]
                if items:
                    logger.info(f"  Found {len(items)} items with selector: {selector}")
                    break
            
            for item in items:
                # Try multiple name selectors
                name_elem = (
                    item.select_one('.plp-product__name') or
                    item.select_one('.pip-header-section__title') or
                    item.select_one('h3') or
                    item.select_one('[class*="product-name"]')
                )
                
                # Try multiple price selectors
                price_elem = (
                    item.select_one('.pip-price__integer') or
                    item.select_one('.pip-temp-price__integer') or
                    item.select_one('[class*="price"]')
                )
                
                if name_elem and price_elem:
                    products.append({
                        'name': name_elem.get_text(strip=True),
                        'price': f"${price_elem.get_text(strip=True)}",
                        'source': 'IKEA'
                    })
            
            data = {
                'competitor': 'IKEA',
                'category': category,
                'products': products,
                'timestamp': datetime.now().isoformat(),
                'url': url,
                'method': 'Selenium (Firefox)'
            }
            
            self.cache[cache_key] = data
            self._save_cache()
            
            logger.info(f"✅ IKEA {category}: {len(products)} products (Selenium)")
            return data
            
        except Exception as e:
            logger.error(f"IKEA scrape failed: {e}")
            return self.cache.get(cache_key, {
                'competitor': 'IKEA',
                'category': category,
                'products': [],
                'error': str(e),
                'method': 'Selenium (failed)'
            })
    
    

    # ═══════════════════════════════════════════════════════════
    #  NEW COMPETITORS
    # ═══════════════════════════════════════════════════════════

    def _scrape_goalzero(self, category: str = "electronics") -> Dict:
        """Scrape Goal Zero (Shopify) - Portable Power / Electronics"""
        collection_map = {
            'electronics': 'power-stations',
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
            collection_handle="all",
            site_name="Taylor Stitch",
            category=category
        )

    def _scrape_chubbies(self, category: str = "clothing") -> Dict:
        """Scrape Chubbies (Shopify) - Men's Casual Clothing"""
        return self._scrape_shopify_collection(
            domain="www.chubbies.com",
            collection_handle="all",
            site_name="Chubbies",
            category=category
        )

    def _scrape_finisterre(self, category: str = "clothing") -> Dict:
        """Scrape Finisterre (Shopify) - Sustainable Outdoor Clothing"""
        return self._scrape_shopify_collection(
            domain="www.finisterre.com",
            collection_handle="all",
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
    
    async def scrape_competitor_pricing_async(self, category: str) -> List[Dict]:
        """
        Scrape multiple competitors for a category
        API/BeautifulSoup scrapers run sequentially with error handling
        Selenium scrapers run sequentially with driver cleanup
        """
        
        logger.info(f"🚀 Scraping competitors for category: {category}")
        start = time.time()
        
        results = []
        scraper_statuses = []  # Track per-scraper status for UI dashboard
        
        # Define scraper methods per category
        scraper_methods = {
            'electronics': [self._scrape_newegg, self._scrape_goalzero],
            'home': [self._scrape_ikea_selenium],
            'clothing': [self._scrape_taylorstitch, self._scrape_chubbies, self._scrape_finisterre],
            'food': [self._scrape_swanson, self._scrape_nativepath],
            'sports': [self._scrape_campmor]
        }
        
        methods = scraper_methods.get(category, [])
        
        # Separate by scraping method
        selenium_methods = [m for m in methods if 'selenium' in m.__name__]
        api_methods = [m for m in methods if m not in selenium_methods]
        
        # Run API/BeautifulSoup scrapers
        if api_methods:
            for method in api_methods:
                scraper_start = time.time()
                try:
                    logger.info(f"🔄 Running {method.__name__}...")
                    result = method(category)
                    elapsed_s = round(time.time() - scraper_start, 2)
                    
                    if result and result.get('products'):
                        logger.info(f"✅ {method.__name__}: {len(result['products'])} products")
                        results.append(result)
                        scraper_statuses.append({
                            'name': result.get('competitor', method.__name__),
                            'status': 'success',
                            'products': len(result['products']),
                            'time': elapsed_s,
                            'error': None
                        })
                    else:
                        logger.warning(f"⚠️  {method.__name__}: No products found")
                        scraper_statuses.append({
                            'name': method.__name__,
                            'status': 'empty',
                            'products': 0,
                            'time': elapsed_s,
                            'error': 'No products returned'
                        })
                        
                except Exception as e:
                    elapsed_s = round(time.time() - scraper_start, 2)
                    logger.error(f"❌ {method.__name__} failed: {str(e)[:200]}")
                    scraper_statuses.append({
                        'name': method.__name__,
                        'status': 'failed',
                        'products': 0,
                        'time': elapsed_s,
                        'error': str(e)[:150]
                    })
                
                time.sleep(0.5)
        
        # Run Selenium scrapers with driver cleanup
        for method in selenium_methods:
            scraper_start = time.time()
            try:
                logger.info(f"🔄 Running {method.__name__}...")
                data = method(category)
                elapsed_s = round(time.time() - scraper_start, 2)
                
                if data and data.get('products'):
                    results.append(data)
                    scraper_statuses.append({
                        'name': data.get('competitor', method.__name__),
                        'status': 'success',
                        'products': len(data['products']),
                        'time': elapsed_s,
                        'error': None
                    })
                else:
                    scraper_statuses.append({
                        'name': method.__name__,
                        'status': 'empty',
                        'products': 0,
                        'time': elapsed_s,
                        'error': 'No products returned'
                    })
                
                # Quit driver after each scrape
                if self._driver:
                    try:
                        self._driver.quit()
                    except:
                        pass
                    finally:
                        self._driver = None
                
                time.sleep(2)
                
            except Exception as e:
                elapsed_s = round(time.time() - scraper_start, 2)
                logger.error(f"❌ {method.__name__} failed: {e}")
                scraper_statuses.append({
                    'name': method.__name__,
                    'status': 'failed',
                    'products': 0,
                    'time': elapsed_s,
                    'error': str(e)[:150]
                })
        
        # Filter empty results
        results = [r for r in results if r and 'products' in r and r['products']]
        
        # Fallback to mock data
        if not results:
            logger.warning(f"All scrapers failed for {category}, using mock data")
            mock = self._get_mock_data(category)
            mock['is_mock'] = True
            results.append(mock)
            scraper_statuses.append({
                'name': 'Mock Data Fallback',
                'status': 'fallback',
                'products': len(mock.get('products', [])),
                'time': 0,
                'error': 'All live scrapers failed — using sample data'
            })
        
        elapsed = time.time() - start
        logger.info(f"✅ Scraped {len(results)} sources for {category} in {elapsed:.2f}s")
        
        return results, scraper_statuses

    
    def scrape_competitor_pricing(self, category: str) -> Dict:
        """
        Synchronous wrapper for async scraping
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        results, scraper_statuses = loop.run_until_complete(self.scrape_competitor_pricing_async(category))
        
        return {
            'category': category,
            'competitors': results,
            'scraper_statuses': scraper_statuses,
            'timestamp': datetime.now().isoformat()
        }
    
    
    # ═══════════════════════════════════════════════════════════
    #  MAIN QUERY METHOD
    # ═══════════════════════════════════════════════════════════
    
    def query(self, question: str, category: str = None) -> Dict:
        """
        Main Web Agent query method
        """
        
        logger.info(f"\n{'='*50}")
        logger.info(f"🌐 WEB AGENT: {question}")
        logger.info(f"{'='*50}")
        
        start_time = time.time()
        
        if category:
            # Category-specific pricing
            pricing_data = self.scrape_competitor_pricing(category)
            
            # Use LLM to answer based on scraped data
            prompt = f"""Based on competitor pricing data, answer this question:

QUESTION: {question}

COMPETITOR DATA:
{json.dumps(pricing_data, indent=2)}

Answer concisely, compare prices across competitors, include price ranges and sources.
Format as bullet points with competitor names."""

            try:
                if self.groq_client:
                    response = self.groq_client.invoke(prompt)
                    quota_tracker.report_success("llama-3.3-70b-versatile")
                    answer = response.content
                else:
                    answer = "Groq unavailable. Raw data:\n" + json.dumps(pricing_data, indent=2)
                    
                elapsed = time.time() - start_time
                
                logger.info(f"✅ Web query complete in {elapsed:.2f}s")
                
                return {
                    'answer': answer,
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
                return {
                    'answer': fallback_answer,
                    'raw_data': pricing_data,
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
        if self._driver:
            try:
                self._driver.quit()
                logger.info("🔌 Selenium driver closed")
            except:
                pass
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