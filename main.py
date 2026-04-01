import json
import asyncio
import re
import os
import httpx
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from playwright.async_api import async_playwright, BrowserContext
from playwright_stealth import Stealth

BASE_URL = "https://kaido.to"
IS_HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"


class Kaido:
    def __init__(self):
        self.playwright = None
        self.context: Optional[BrowserContext] = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir="./browser_data",
            headless=IS_HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--autoplay-policy=no-user-gesture-required",
                "--mute-audio",
            ],
            ignore_https_errors=True,
        )

    async def stop(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    def _map_server_name(self, name: str) -> str:
        name = name.lower()
        if "vidstreaming" in name:
            return "hd-1"
        if "vidcloud" in name:
            return "hd-2"
        return name

    async def _fetch_anilist_metadata(self, title: str):
        """Helper function to fetch AniList ID, MAL ID, and accurate Scores from AniList GraphQL"""
        query = """
        query ($search: String) {
          Media (search: $search, type: ANIME) {
            id
            idMal
            averageScore
          }
        }
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://graphql.anilist.co",
                    json={"query": query, "variables": {"search": title}},
                    timeout=5.0,
                )
                if response.status_code == 200:
                    data = response.json().get("data", {}).get("Media")
                    if data:
                        return data
        except Exception:
            pass
        return None

    # ---------------- HOME ----------------
    async def get_home(self):
        page = await self.context.new_page()
        await page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded")

        home_data = await page.evaluate("""
        () => {
            const safeText = (el, sel) => el.querySelector(sel)?.innerText?.trim() || null;
            const safeAttr = (el, sel, attr) => el.querySelector(sel)?.getAttribute(attr) || null;

            const parseItem = (el) => {
                if (!el) return null;
                const a = el.querySelector(".film-name a") || el.querySelector("a");
                if (!a) return null;
                const id = a.href?.split("/").pop().split("?")[0];
                if (!id) return null;
                
                const sub = el.querySelector(".tick-sub")?.innerText?.replace(/[^0-9]/g, '');
                const dub = el.querySelector(".tick-dub")?.innerText?.replace(/[^0-9]/g, '');
                const eps = el.querySelector(".tick-eps")?.innerText?.replace(/[^0-9]/g, '');

                return {
                    id: id,
                    title: a.innerText?.trim() || a.getAttribute("title"),
                    japanese_title: a.getAttribute("data-jname") || null,
                    poster: safeAttr(el, "img", "data-src") || safeAttr(el, "img", "src"),
                    episodes: {
                        sub: sub ? parseInt(sub) : null,
                        dub: dub ? parseInt(dub) : null,
                        total: eps ? parseInt(eps) : null
                    },
                    type: el.querySelector(".fd-infor .fdi-item:not(.fdi-duration)")?.innerText?.trim() || null
                };
            };

            const getSection = (primary, fallback) => {
                let items = document.querySelectorAll(primary);
                if (items.length === 0 && fallback) items = document.querySelectorAll(fallback);
                return [...items].map(parseItem).filter(x => x && x.id);
            };

            const spotlight = [...document.querySelectorAll("#slider .swiper-slide")].map(el => {
                const a = el.querySelector(".desi-buttons a");
                return {
                    id: a?.href?.split("/").pop().split("?")[0],
                    title: safeText(el, ".desi-head-title"),
                    japanese_title: safeAttr(el, ".desi-head-title", "data-jname"),
                    poster: safeAttr(el, "img.film-poster-img", "data-src") || safeAttr(el, "img.film-poster-img", "src"),
                    description: safeText(el, ".desi-description"),
                    type: safeText(el, ".sc-detail .scd-item:nth-child(1)")
                };
            }).filter(x => x && x.id);

            const trending = [...document.querySelectorAll("#trending-home .swiper-slide")].map(el => {
                const a = el.querySelector(".film-title a") || el.querySelector("a");
                return {
                    id: a?.href?.split("/").pop().split("?")[0],
                    title: safeText(el, ".film-title"),
                    japanese_title: a?.getAttribute("data-jname") || null,
                    poster: safeAttr(el, "img.film-poster-img", "data-src") || safeAttr(el, "img.film-poster-img", "src"),
                    rank: parseInt(safeText(el, ".number")?.replace(/[^0-9]/g, '')) || null
                };
            }).filter(x => x && x.id);

            const latest_episodes = getSection("#recently-updated .flw-item", ".block_area_home:nth-of-type(1) .flw-item");
            const new_added = getSection("#recently-added .flw-item", ".block_area_home:nth-of-type(2) .flw-item");
            const top_upcoming = getSection("#top-upcoming .flw-item", ".block_area_home:nth-of-type(3) .flw-item");

            const parseTop10 = (selector) => [...document.querySelectorAll(selector)].map(el => {
                const a = el.querySelector(".film-name a") || el.querySelector(".film-detail a") || el.querySelector("a");
                if (!a) return null;
                const id = a.href?.split("/").pop().split("?")[0];
                if (!id) return null;
                
                const sub = el.querySelector(".tick-sub")?.innerText?.replace(/[^0-9]/g, '');
                const dub = el.querySelector(".tick-dub")?.innerText?.replace(/[^0-9]/g, '');
                const eps = el.querySelector(".tick-eps")?.innerText?.replace(/[^0-9]/g, '');

                return {
                    id: id,
                    title: a.innerText?.trim() || a.getAttribute("title"),
                    japanese_title: a.getAttribute("data-jname") || null,
                    poster: safeAttr(el, "img", "data-src") || safeAttr(el, "img", "src"),
                    rank: parseInt(safeText(el, ".film-number span, .rank")) || null,
                    episodes: {
                        sub: sub ? parseInt(sub) : null,
                        dub: dub ? parseInt(dub) : null,
                        total: eps ? parseInt(eps) : null
                    }
                };
            }).filter(x => x && x.id);

            const top_10 = {
                today: parseTop10("#top-viewed-day ul li"),
                week: parseTop10("#top-viewed-week ul li"),
                month: parseTop10("#top-viewed-month ul li")
            };

            const genres = [...document.querySelectorAll(".sb-genre-list li a, .genre-list li a")].map(el => el.innerText.trim()).filter(Boolean);

            return { spotlight, trending, latest_episodes, new_added, top_upcoming, top_10, genres };
        }
        """)

        await page.close()
        return home_data

    # ---------------- SEARCH ----------------
    async def search(self, q: str):
        page = await self.context.new_page()
        await page.goto(f"{BASE_URL}/search?keyword={q}", wait_until="domcontentloaded")

        results = await page.evaluate("""
        () => {
            return [...document.querySelectorAll(".film_list-wrap .flw-item")].map(el => {
                const a = el.querySelector(".film-name a") || el.querySelector("a");
                const id = a?.href?.split("/").pop().split("?")[0];
                const title = a?.innerText?.trim() || a?.getAttribute("title");
                const jname = a?.getAttribute("data-jname");
                
                const posterEl = el.querySelector(".film-poster img");
                const poster = posterEl?.getAttribute("data-src") || posterEl?.src;
                
                const rate = el.querySelector(".tick-rate")?.innerText?.trim();
                
                const sub = el.querySelector(".tick-sub")?.innerText?.replace(/[^0-9]/g, '');
                const dub = el.querySelector(".tick-dub")?.innerText?.replace(/[^0-9]/g, '');
                const eps = el.querySelector(".tick-eps")?.innerText?.replace(/[^0-9]/g, '');
                
                const type = el.querySelector(".fd-infor .fdi-item:not(.fdi-duration)")?.innerText?.trim();
                const duration = el.querySelector(".fd-infor .fdi-duration")?.innerText?.trim();

                return {
                    id: id,
                    title: title,
                    japanese_title: jname || null,
                    poster: poster || null,
                    rating: rate || null,
                    episodes: {
                        sub: sub ? parseInt(sub) : null,
                        dub: dub ? parseInt(dub) : null,
                        total: eps ? parseInt(eps) : null
                    },
                    type: type || null,
                    duration: duration || null
                };
            }).filter(x => x.id);
        }
        """)

        await page.close()
        return {"query": q, "total": len(results), "results": results}

    # ---------------- INFO ----------------
    # ---------------- INFO ----------------
    async def get_info(self, anime_id: str):
        page = await self.context.new_page()
        await page.goto(f"{BASE_URL}/{anime_id}", wait_until="domcontentloaded")

        # Scroll to the bottom of the page to trigger Kaido's lazy-loading
        # for the "Recommended" section and Images.
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        await asyncio.sleep(2.5)

        data = await page.evaluate("""
        () => {
            const safeText = (document, sel) => document.querySelector(sel)?.innerText?.trim() || null;
            
            const info = {
                title: safeText(document, ".anisc-detail .film-name") || safeText(document, "h1"),
                japanese_title: document.querySelector(".anisc-detail .film-name")?.getAttribute("data-jname") || null,
                description: null,
                poster: document.querySelector(".film-poster img")?.src || null,
                mal_score: null,
                anilist_id: null,
                mal_id: null,
                stats: {
                    rating: null,
                    quality: null,
                    episodes: { sub: null, dub: null, total: null },
                    type: null,
                    duration: null
                },
                more_info: {},
                genres: [],
                producers: [],
                studios: [],
                seasons: [],
                recommended: [],
                most_popular: []
            };

            // Parse Description & clean out spam
            let desc = safeText(document, ".film-description .text");
            if (desc) {
                desc = desc.split("Kaido is the best site")[0].trim();
                desc = desc.replace(/\\+ More$/, "").trim();
                info.description = desc;
            }

            // Parse Stats (PG Rating, Quality, Sub, Dub, Eps, Type, Duration)
            const tickPg = document.querySelector(".tick-item.tick-pg");
            if (tickPg) info.stats.rating = tickPg.innerText.trim();

            const tickQuality = document.querySelector(".tick-item.tick-quality");
            if (tickQuality) info.stats.quality = tickQuality.innerText.trim();

            const tickSub = document.querySelector(".tick-item.tick-sub");
            if (tickSub) info.stats.episodes.sub = parseInt(tickSub.innerText.replace(/[^0-9]/g, ''));

            const tickDub = document.querySelector(".tick-item.tick-dub");
            if (tickDub) info.stats.episodes.dub = parseInt(tickDub.innerText.replace(/[^0-9]/g, ''));

            const tickEps = document.querySelector(".tick-item.tick-eps");
            if (tickEps) info.stats.episodes.total = parseInt(tickEps.innerText.replace(/[^0-9]/g, ''));

            document.querySelectorAll(".film-stats .item").forEach(span => {
                const text = span.innerText.trim();
                if (text && !span.className.includes("tick-")) {
                    if (/\\dm$/.test(text) || text.includes("m")) info.stats.duration = text;
                    else if (['TV', 'Movie', 'OVA', 'ONA', 'Special'].includes(text)) info.stats.type = text;
                }
            });

            // Parse Sidebar details
            document.querySelectorAll(".anisc-info .item").forEach(item => {
                const headEl = item.querySelector(".item-head");
                if (!headEl) return;
                const key = headEl.innerText.replace(":", "").trim().toLowerCase().replace(/ /g, "_");
                
                const aTags = item.querySelectorAll("a");
                if (key === "genres") {
                    info.genres = [...aTags].map(a => a.innerText.trim());
                } else if (key === "producers") {
                    info.producers = [...aTags].map(a => a.innerText.trim());
                } else if (key === "studios") {
                    info.studios = [...aTags].map(a => a.innerText.trim());
                } else {
                    let val = item.querySelector(".name")?.innerText.trim();
                    if (!val) {
                        val = item.innerText.replace(headEl.innerText, "").trim();
                    }
                    if (key === "mal_score" || key === "score") {
                        info.mal_score = parseFloat(val) || val;
                    } else {
                        info.more_info[key] = val;
                    }
                }
            });

            // Check if DOM holds MAL or AniList IDs
            const syncMal = document.querySelector("[data-sync='mal'], [data-mal-id]");
            if (syncMal) info.mal_id = parseInt(syncMal.getAttribute("data-mal-id") || syncMal.getAttribute("data-id"));
            
            const syncAni = document.querySelector("[data-sync='anilist'], [data-anilist-id]");
            if (syncAni) info.anilist_id = parseInt(syncAni.getAttribute("data-anilist-id") || syncAni.getAttribute("data-id"));

            // Parse Seasons List (With advanced image parsing)
            document.querySelectorAll(".os-list a").forEach(a => {
                let pUrl = null;
                let bgEl = a.querySelector('.season-poster, .os-poster, div[style*="background"]');
                if (bgEl) {
                    let style = bgEl.getAttribute('style') || '';
                    let match = style.match(/url\\(['"]?(.*?)['"]?\\)/);
                    if (match) pUrl = match[1];
                }
                if (!pUrl) {
                    let img = a.querySelector('img');
                    if (img) pUrl = img.getAttribute('data-src') || img.src;
                }
                
                info.seasons.push({
                    id: a.href.split("/").pop().split("?")[0],
                    title: a.getAttribute("title") || a.innerText.trim(),
                    is_current: a.classList.contains("active"),
                    poster: pUrl // Note: If Kaido only has text buttons for seasons, this will be null.
                });
            });

            // Helper to parse mini-items (Recommended & Popular)
            const parseMiniItem = (el) => {
                if (!el) return null;
                const a = el.querySelector(".film-name a, .dynamic-name, .film-detail a, .film-title a");
                if (!a) return null;
                const id = a.href?.split("/").pop().split("?")[0];
                if (!id) return null;
                
                const sub = el.querySelector(".tick-sub")?.innerText?.replace(/[^0-9]/g, '');
                const dub = el.querySelector(".tick-dub")?.innerText?.replace(/[^0-9]/g, '');
                const eps = el.querySelector(".tick-eps")?.innerText?.replace(/[^0-9]/g, '');
                
                // Aggressive Type Scraper (Looks through all spans to find TV/Movie/OVA)
                let itemType = null;
                el.querySelectorAll('.fdi-item, .tick-item, .type, span').forEach(node => {
                    let txt = node.innerText.trim();
                    if (['TV', 'Movie', 'OVA', 'ONA', 'Special', 'Music'].includes(txt)) {
                        itemType = txt;
                    }
                });
                
                return {
                    id: id,
                    title: a.innerText?.trim() || a.getAttribute("title"),
                    japanese_title: a.getAttribute("data-jname") || null,
                    poster: el.querySelector("img")?.getAttribute("data-src") || el.querySelector("img")?.src || null,
                    type: itemType,
                    episodes: {
                        sub: sub ? parseInt(sub) : null,
                        dub: dub ? parseInt(dub) : null,
                        total: eps ? parseInt(eps) : null
                    }
                };
            };

            // DYNAMICALLY FIND "RECOMMENDED" SECTION
            let recItems = [];
            document.querySelectorAll("h2, .cat-heading").forEach(h => {
                if (h.innerText.toLowerCase().includes("recommended")) {
                    let container = h.closest(".block_area, section, div.container, .wrap");
                    if (container) {
                        let items = container.querySelectorAll(".flw-item");
                        if (items.length > 0) recItems = Array.from(items);
                    }
                }
            });
            if (recItems.length === 0) recItems = document.querySelectorAll("#anime-recommended .flw-item"); // Fallback
            info.recommended = [...recItems].map(parseMiniItem).filter(x => x && x.id);

            // DYNAMICALLY FIND "MOST POPULAR" SECTION
            let popItems = [];
            document.querySelectorAll("h2, .cat-heading").forEach(h => {
                if (h.innerText.toLowerCase().includes("most popular")) {
                    let container = h.closest(".block_area, section, .sidebar");
                    if (container) {
                        let items = container.querySelectorAll("ul li, .ulclear li");
                        if (items.length > 0) popItems = Array.from(items);
                    }
                }
            });
            if (popItems.length === 0) popItems = document.querySelectorAll("#toppopular ul li, .mop-list li, .sidebar-list li"); // Fallback
            info.most_popular = [...popItems].map(parseMiniItem).filter(x => x && x.id);

            return info;
        }
        """)
        await page.close()

        # Fallback: Query AniList GraphQL to fetch IDs and Score if missing or to augment data
        title_to_search = data.get("japanese_title") or data.get("title")
        if title_to_search and (
            not data.get("anilist_id") or not data.get("mal_score")
        ):
            anilist_data = await self._fetch_anilist_metadata(title_to_search)
            if anilist_data:
                data["anilist_id"] = data.get("anilist_id") or anilist_data.get("id")
                data["mal_id"] = data.get("mal_id") or anilist_data.get("idMal")

                # AniList average score is out of 100, convert to MAL scale (out of 10)
                score_100 = anilist_data.get("averageScore")
                if score_100 and not data.get("mal_score"):
                    data["mal_score"] = score_100 / 10

        return {"id": anime_id, **data}

    # ---------------- EPISODES ----------------
    async def get_episodes(self, anime_id: str):
        page = await self.context.new_page()
        numeric_id = anime_id.split("-")[-1]

        try:
            await page.goto(f"{BASE_URL}/{anime_id}", wait_until="domcontentloaded")
            episodes = await page.evaluate(
                f"""
            async (id) => {{
                try {{
                    let resp = await fetch(`/ajax/v2/episode/list/${{id}}`, {{ headers: {{ "X-Requested-With": "XMLHttpRequest" }} }});
                    let data = await resp.json().catch(()=>({{}}));
                    if (!data.html && !data.result) {{
                        resp = await fetch(`/ajax/episode/list/${{id}}`, {{ headers: {{ "X-Requested-With": "XMLHttpRequest" }} }});
                        data = await resp.json().catch(()=>({{}}));
                    }}
                    const htmlContent = data.html || data.result || data.data;
                    if (htmlContent) {{
                        const div = document.createElement("div"); div.innerHTML = htmlContent;
                        const eps = [];
                        div.querySelectorAll("a[data-id], .ep-item[data-id]").forEach(el => {{
                            const num = el.getAttribute("data-number") || el.getAttribute("data-num");
                            const epId = el.getAttribute("data-id");
                            if (num && epId) eps.push({{ episode: parseFloat(num), id: epId, title: el.getAttribute("title") || el.innerText.trim() }});
                        }});
                        return eps;
                    }}
                }} catch (e) {{ }} return [];
            }}
            """,
                numeric_id,
            )
            unique_eps = {ep["id"]: ep for ep in episodes}.values()
            episodes = sorted(unique_eps, key=lambda x: x["episode"])
        finally:
            await page.close()
        return {"id": anime_id, "total": len(episodes), "episodes": episodes}

    # ---------------- SERVERS ----------------
    async def get_servers(self, anime_id: str, ep: str):
        page = await self.context.new_page()
        try:
            await page.goto(f"{BASE_URL}/{anime_id}", wait_until="domcontentloaded")
            servers_data = await page.evaluate(
                f"""
                async (epId) => {{
                    try {{
                        let res = await fetch(`/ajax/v2/episode/servers?episodeId=${{epId}}`, {{ headers: {{"X-Requested-With": "XMLHttpRequest"}} }});
                        let data = await res.json().catch(()=>({{}}));
                        if (!data.html && !data.result) {{
                            res = await fetch(`/ajax/episode/servers?episodeId=${{epId}}`, {{ headers: {{"X-Requested-With": "XMLHttpRequest"}} }});
                            data = await res.json().catch(()=>({{}}));
                        }}
                        const div = document.createElement('div'); div.innerHTML = data.html || data.result || data.data || "";
                        const results = {{ sub: [], dub: [], raw: [] }};
                        div.querySelectorAll('.server-item, .server, .item.server').forEach(el => {{
                            let type = el.getAttribute('data-type');
                            if (!type) {{
                                const parent = el.closest('.servers-sub, .servers-dub, .servers-raw, [data-type]');
                                if (parent) {{
                                    if (parent.classList.contains('servers-sub')) type = 'sub';
                                    else if (parent.classList.contains('servers-dub')) type = 'dub';
                                    else type = parent.getAttribute('data-type');
                                }}
                            }}
                            type = (type || 'sub').toLowerCase().trim();
                            if (!results[type]) results[type] = [];
                            let serverId = el.getAttribute('data-id') || el.getAttribute('data-server-id');
                            if (!serverId) {{
                                const child = el.querySelector('[data-id], [data-server-id]');
                                if (child) serverId = child.getAttribute('data-id') || child.getAttribute('data-server-id');
                            }}
                            const serverName = (el.innerText || '').trim().toLowerCase();
                            if (serverId && serverName) results[type].push({{ serverName, serverId }});
                        }});
                        return results;
                    }} catch (err) {{ return {{ sub: [], dub: [], raw: [], error: err.message }}; }}
                }}
            """,
                ep,
            )
            for t in ["sub", "dub", "raw"]:
                if t in servers_data:
                    for s in servers_data[t]:
                        s["serverName"] = self._map_server_name(s["serverName"])
            return {"episode": ep, "servers": servers_data}
        finally:
            await page.close()

    # ---------------- RESOLVE ----------------
    async def resolve(self, anime_id: str, ep: str, req_type: str, req_server: str):
        page = await self.context.new_page()
        await Stealth().apply_stealth_async(page)

        m3u8_link = None
        embed_link = None

        stream_data = {
            "intro": {"start": 0, "end": 0},
            "outro": {"start": 0, "end": 0},
            "tracks": [],
        }

        try:
            await page.goto(f"{BASE_URL}/{anime_id}", wait_until="domcontentloaded")

            # 1. Fetch Servers
            servers_data = await page.evaluate(
                f"""
                async (epId) => {{
                    try {{
                        let res = await fetch(`/ajax/v2/episode/servers?episodeId=${{epId}}`, {{ headers: {{"X-Requested-With": "XMLHttpRequest"}} }});
                        let data = await res.json().catch(()=>({{}}));
                        if (!data.html && !data.result) {{
                            res = await fetch(`/ajax/episode/servers?episodeId=${{epId}}`, {{ headers: {{"X-Requested-With": "XMLHttpRequest"}} }});
                            data = await res.json().catch(()=>({{}}));
                        }}
                        const div = document.createElement('div'); div.innerHTML = data.html || data.result || data.data || "";
                        const results = {{ sub: [], dub: [], raw: [] }};
                        div.querySelectorAll('.server-item, .server, .item.server').forEach(el => {{
                            let t = el.getAttribute('data-type');
                            if (!t) {{
                                const parent = el.closest('.servers-sub, .servers-dub, .servers-raw');
                                if (parent) t = parent.classList.contains('servers-sub') ? 'sub' : 'dub';
                            }}
                            t = (t || 'sub').toLowerCase().trim();
                            if (!results[t]) results[t] = [];
                            let serverId = el.getAttribute('data-id') || el.getAttribute('data-server-id');
                            if (!serverId) {{
                                const child = el.querySelector('[data-id], [data-server-id]');
                                if (child) serverId = child.getAttribute('data-id') || child.getAttribute('data-server-id');
                            }}
                            const serverName = (el.innerText || '').trim().toLowerCase();
                            if (serverId && serverName) results[t].push({{ serverName, serverId }});
                        }});
                        return results;
                    }} catch (e) {{ return {{ sub: [], dub: [] }}; }}
                }}
            """,
                ep,
            )

            target_list = servers_data.get(req_type.lower(), [])
            actual_type = req_type.lower()

            if not target_list and servers_data.get("sub"):
                target_list = servers_data["sub"]
                actual_type = "sub"

            if not target_list:
                return {"error": "No servers available for this episode."}

            available_servers = []
            for s in target_list:
                mapped = self._map_server_name(s["serverName"])
                available_servers.append(
                    {"serverName": mapped, "serverId": s["serverId"]}
                )

            # 2. Extract Server Match
            server_id = None
            req_server_lower = req_server.lower()
            matched_server_name = None

            for i, s in enumerate(target_list):
                raw_name = s["serverName"].lower()
                mapped_name = available_servers[i]["serverName"]
                if req_server_lower in raw_name or req_server_lower == mapped_name:
                    server_id = s["serverId"]
                    matched_server_name = mapped_name
                    break

            if not server_id:
                server_id = available_servers[0]["serverId"]
                matched_server_name = available_servers[0]["serverName"]

            # 3. Fetch Embed Link
            embed_data = await page.evaluate(
                f"""
                async (sId) => {{
                    try {{
                        let res = await fetch(`/ajax/v2/episode/sources?id=${{sId}}`, {{ headers: {{"X-Requested-With": "XMLHttpRequest"}} }});
                        let data = await res.json().catch(()=>({{}}));
                        if (!data.link) {{
                            res = await fetch(`/ajax/episode/sources?id=${{sId}}`, {{ headers: {{"X-Requested-With": "XMLHttpRequest"}} }});
                            data = await res.json().catch(()=>({{}}));
                        }}
                        return data;
                    }} catch (e) {{ return {{ error: e.message }}; }}
                }}
            """,
                server_id,
            )

            embed_link = embed_data.get("link")
            if not embed_link:
                return {
                    "error": "Could not extract embed link from the selected server."
                }

            if "?" in embed_link:
                embed_link += "&z=&autoPlay=1&oa=1&asi=1&_debug=false"
            else:
                embed_link += "?z=&autoPlay=1&oa=1&asi=1&_debug=false"

            # 4. Aggressive Network Interceptors
            def capture_request(req):
                nonlocal m3u8_link
                url = req.url
                if ".m3u8" in url and "ping" not in url:
                    if not m3u8_link:
                        m3u8_link = url

            async def capture_response(res):
                try:
                    if (
                        res.request.method != "OPTIONS"
                        and "application/json" in res.headers.get("content-type", "")
                    ):
                        data = await res.json()
                        if isinstance(data, dict):
                            if (
                                "tracks" in data
                                and isinstance(data["tracks"], list)
                                and len(data["tracks"]) > 0
                            ):
                                stream_data["tracks"] = data["tracks"]
                            if "intro" in data and data["intro"]:
                                stream_data["intro"] = data["intro"]
                            if "outro" in data and data["outro"]:
                                stream_data["outro"] = data["outro"]
                except:
                    pass

            page.on("request", capture_request)
            page.on("response", capture_response)

            # 5. Rip the stream
            await page.goto(
                embed_link, referer=f"{BASE_URL}/", wait_until="domcontentloaded"
            )

            for _ in range(12):
                if m3u8_link:
                    break
                await page.evaluate("""
                () => {
                    const rPlay = document.getElementById('click-to-play');
                    if (rPlay) rPlay.click();
                    const jwPlay = document.querySelector('.jw-video, .jw-button-color, .jw-icon-display, .play-btn');
                    if (jwPlay) jwPlay.click();
                    document.querySelectorAll('video').forEach(v => {
                        v.muted = false;
                        v.play().catch(()=>{});
                    });
                }
                """)
                await asyncio.sleep(0.75)

            # 6. Fallback Track Extraction
            if not stream_data["tracks"]:
                stream_data["tracks"] = await page.evaluate("""
                () => {
                    let extracted = [];
                    try {
                        if (typeof jwplayer === 'function') {
                            const config = jwplayer().getConfig();
                            if (config && config.tracks && config.tracks.length > 0) {
                                extracted = config.tracks.map(t => ({
                                    file: t.file, label: t.label || t.name || "English",
                                    kind: t.kind || "captions", default: t.default || false
                                }));
                            }
                        }
                    } catch(e) {}
                    
                    if (extracted.length === 0) {
                        extracted = Array.from(document.querySelectorAll('track')).map(t => ({
                            file: t.src, label: t.label || t.srclang || "English",
                            kind: t.kind || "captions", default: t.default || false
                        }));
                    }
                    return extracted.filter(t => t.file && t.kind !== "thumbnails");
                }
                """)

        except Exception as e:
            return {"episode": ep, "error": f"An error occurred: {str(e)}"}
        finally:
            await page.close()

        if not m3u8_link:
            return {
                "episode": ep,
                "type": actual_type,
                "server": matched_server_name,
                "error": "Embed loaded, but no m3u8 stream was detected.",
            }

        # ---------------- FORMAT TRACKS & PRIORITIZE ENGLISH ONLY ----------------
        clean_tracks = []
        for track in stream_data.get("tracks", []):
            label = track.get("label", "English")
            # Only append valid VTT subtitle tracks, remove image sprites, AND enforce English only
            if track.get("kind") != "thumbnails" and track.get("file"):
                if "english" in label.lower() or label.lower() == "en":
                    clean_tracks.append(
                        {
                            "file": track.get("file"),
                            "label": label,
                            "kind": track.get("kind", "captions"),
                            "default": True,  # Force the English track to default to True
                        }
                    )

        # 7. Final Output
        return {
            "episode": ep,
            "type": actual_type,
            "embed_url": embed_link,
            "available_servers": available_servers,
            "sources": [{"file": m3u8_link, "type": "hls"}],
            "tracks": clean_tracks,
            "encrypted": False,
            "intro": stream_data.get("intro", {"start": 0, "end": 0}),
            "outro": stream_data.get("outro", {"start": 0, "end": 0}),
            "server": matched_server_name,
        }


kaido = Kaido()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await kaido.start()
    yield
    await kaido.stop()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=JSONResponse)
async def root():
    return {"status": "ok", "message": "Kaido API is running!"}


@app.get("/home")
async def api_home():
    return await kaido.get_home()


@app.get("/search")
async def api_search(q: str):
    return await kaido.search(q)


@app.get("/info/{anime_id}")
async def api_info(anime_id: str):
    return await kaido.get_info(anime_id)


@app.get("/episodes/{anime_id}")
async def api_episodes(anime_id: str):
    return await kaido.get_episodes(anime_id)


@app.get("/servers/{anime_id}")
async def api_servers(anime_id: str, ep: str = Query(...)):
    return await kaido.get_servers(anime_id, ep)


@app.get("/resolve/{anime_id}")
async def api_resolve(
    anime_id: str,
    ep: str = Query(...),
    type: str = Query("sub", description="'sub' or 'dub'"),
    server: str = Query("hd-1", description="'hd-1' (vidstreaming), 'hd-2' (vidcloud)"),
):
    return await kaido.resolve(anime_id, ep, type, server)


@app.get("/seasons/{anime_id}")
async def api_seasons(anime_id: str):
    return await kaido.get_seasons(anime_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7860)
