#!/usr/bin/env bash
# download_corpus.sh — Fetch open-access literature for SandbeltOS RAG corpus.
#
# Downloads ~35 candidate PDFs into backend/rag/docs/{gov,papers_cn,papers_en}/
# and writes manifest.json listing what succeeded.
#
# Usage:
#   bash backend/rag/download_corpus.sh
#
# Idempotent — re-running skips files already present and re-tries only the
# missing ones.

set -u  # do NOT use -e; one bad URL shouldn't abort the batch

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
ROOT="$(cd "$(dirname "$0")/docs" && pwd)"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT=45
MANIFEST="$ROOT/manifest.json"
LOG="$ROOT/download.log"

mkdir -p "$ROOT/gov" "$ROOT/papers_cn" "$ROOT/papers_en" "$ROOT/standards"
: >"$LOG"

# ------------------------------------------------------------------
# Corpus entries — one per line: CATEGORY|FILENAME|URL|TITLE
# Categories: gov | papers_cn | papers_en | standards
# ------------------------------------------------------------------
entries=(
  # ---------- Government / 官方文档 ----------
  "gov|three-north-development-report-1978-2018.pdf|https://www.forestry.gov.cn/html/sbj/sbj_5102/20220125154748720366588/file/20220419084114310665949.pdf|三北防护林体系建设发展报告（1978-2018）"
  "gov|three-north-phase4-plan.pdf|https://www.ndrc.gov.cn/fggz/fzzlgh/gjjzxgh/200709/P020191104623220585491.pdf|三北防护林体系建设四期工程规划"
  "gov|three-north-monitoring-indicators.pdf|https://www.forestry.gov.cn/html/sbj/sbj_5283/20200421113148624935210/file/20200421113210094462687.pdf|三北防护林体系建设监测评价指标研究"
  "gov|three-north-40-year-series.pdf|http://www.forestry.gov.cn.cdn20.com/html/sbj/sbj_5068/20220328155656320356329/file/20220328155756345476917.pdf|三北防护林体系建设40年系列丛书"
  "gov|three-north-scientific-greening-strategy.pdf|https://zglyjj.nefu.edu.cn/cn/article/pdf/preview/10.13691/j.cnki.cn23-1539/f.2023.04.005.pdf|三北防护林工程科学绿化策略研究"

  # ---------- Chinese papers (OA) ----------
  "papers_cn|pku-three-north-economic-benefits.pdf|https://ccj.pku.edu.cn/Article/DownLoad?id=621278680965189&type=ArticleFile|三北防护林的长期经济效益"

  # ---------- MDPI Remote Sensing / Land / Sustainability / Forests / Water ----------
  "papers_en|2023_li_otindag_desertification_30yr.pdf|https://www.mdpi.com/2072-4292/15/1/279/pdf|Spatio-Temporal Patterns and Driving Forces of Desertification in Otindag Sandy Land"
  "papers_en|2024_wang_three-north_npp_2decades.pdf|https://www.mdpi.com/2071-1050/16/9/3656/pdf|Quantitative Assessment of Three-North Shelter Forest NPP Two Decades"
  "papers_en|2021_forest-changes_precipitation-zones_three-north.pdf|https://www.mdpi.com/2072-4292/13/4/543/pdf|Forest Changes by Precipitation Zones in Northern China Three-North"
  "papers_en|2022_vegetation_ecological_quality_three-north.pdf|https://www.mdpi.com/2072-4292/14/22/5708/pdf|Improved Vegetation Ecological Quality Three-North Shelterbelt 2000-2020"
  "papers_en|2021_detecting_forest_degradation_three-north.pdf|https://www.mdpi.com/2072-4292/13/6/1131/pdf|Detecting Forest Degradation Three-North Multi-Scale Satellite"
  "papers_en|2022_landuse_vegetation_three-north_2000-2020.pdf|https://www.mdpi.com/2071-1050/14/24/16489/pdf|Temporal Spatial Land Use Vegetation Three-North 2000-2020"
  "papers_en|2025_drought_afforestation_npp_yellow-river.pdf|https://www.mdpi.com/2072-4292/17/12/2100/pdf|Drought Amplifies Suppressive Effect Afforestation NPP Yellow River"
  "papers_en|2025_afforestation_soil-conservation_carbon_shelterbelt.pdf|https://www.mdpi.com/2072-4292/17/20/3455/pdf|Afforestation Impacts Soil Conservation Carbon Sequestration Shelterbelt"
  "papers_en|2024_pioneer_plants_mobile_dunes.pdf|https://www.mdpi.com/2071-1050/16/20/8771/pdf|Vegetation Growth Physiological Adaptation Pioneer Plants Mobile Sand Dunes"
  "papers_en|2024_hunshandake_vegetation_degradation_risk.pdf|https://www.mdpi.com/2073-4441/16/16/2258/pdf|Risk Assessment Vegetation Ecological Degradation Hunshandake Sandy Land"
  "papers_en|2025_wind_erosion_inner_mongolia_1990-2022.pdf|https://www.mdpi.com/2072-4292/17/14/2365/pdf|Spatiotemporal Dynamics Soil Wind Erosion Inner Mongolia"
  "papers_en|2025_wind_erosion_aral_rweq_gee.pdf|https://www.mdpi.com/2072-4292/17/16/2788/pdf|Wind Erosion Aral Sea RWEQ on Google Earth Engine"
  "papers_en|2019_wind_erosion_semiarid_sandy_inner_mongolia.pdf|https://www.mdpi.com/2071-1050/11/1/188/pdf|Wind Erosion Changes Semi-Arid Sandy Area Inner Mongolia"
  "papers_en|2020_soil_wind_erosion_central_asia_gee.pdf|https://www.mdpi.com/2072-4292/12/20/3430/pdf|Quantitative Soil Wind Erosion Potential Central Asia GEE"
  "papers_en|2021_cropland_evolution_wind_erosion_inner_mongolia.pdf|https://www.mdpi.com/2073-445X/10/6/583/pdf|Impact of Cropland Evolution on Soil Wind Erosion Inner Mongolia"
  "papers_en|2021_horqin_land_vegetation.pdf|https://www.mdpi.com/2073-445X/10/1/80/pdf|Horqin Sandy Land Vegetation Remote Sensing"
  "papers_en|2022_ulmus_caragana_transpiration_bashang.pdf|https://www.mdpi.com/1999-4907/13/7/1081/pdf|Canopy Transpiration Stomatal Conductance Ulmus Caragana Bashang"
  "papers_en|2017_soil_microbial_afforestation_loess.pdf|https://www.mdpi.com/1660-4601/14/8/948/pdf|Soil Microbial Community Afforestation Loess Plateau"
  "papers_en|2025_vegetation_restoration_arid_china.pdf|https://www.mdpi.com/2079-7737/14/1/23/pdf|Optimizing Vegetation Restoration Abandoned Mining Arid China"

  # ---------- Nature portfolio (OA) ----------
  "papers_en|2024_hunshandake_sand_fixation_plantations.pdf|https://www.nature.com/articles/s41598-024-78949-4.pdf|Sand Fixation Plantations Soil Properties Hunshandake"
  "papers_en|2024_afforestation_nw_china_carbon_precipitation.pdf|https://www.nature.com/articles/s43247-024-01733-9.pdf|Precipitation Carbon Sequestration Afforestation NW China"
  "papers_en|2025_populus_simoni_liaoning_sandy.pdf|https://www.nature.com/articles/s41598-025-86215-4.pdf|Populus simoni Plantations Liaoning Sandy Area"
  "papers_en|2025_populus_euphratica_tarim_water.pdf|https://www.nature.com/articles/s41598-025-24001-y.pdf|Populus euphratica Water Uptake Tarim River"

  # ---------- Frontiers (OA) ----------
  "papers_en|2023_temperate_savanna_species_richness.pdf|https://www.frontiersin.org/journals/environmental-science/articles/10.3389/fenvs.2023.1112779/pdf|Temperate Savanna Restoration Species Richness"
  "papers_en|2022_regional_wind_erosion_wind_data.pdf|https://www.frontiersin.org/journals/environmental-science/articles/10.3389/fenvs.2022.847128/pdf|Effect of Wind Data Type on Regional Wind Erosion"
  "papers_en|2022_decreasing_soil_erosion_ne_inner_mongolia.pdf|https://www.frontiersin.org/articles/10.3389/feart.2022.988521/pdf|Decreasing Soil Erosion NE Inner Mongolia 40 Years"
  "papers_en|2024_caragana_drought_loess_plateau.pdf|https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2024.1357472/pdf|Caragana korshinskii Drought Response Loess Plateau"
  "papers_en|2023_afforestation_soil_water_alxa.pdf|https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2023.1273108/pdf|Afforestation Soil Water Carbon Alxa Plateau"

  # ---------- PLOS ----------
  "papers_en|2016_drought_landcover_npp_three-north.pdf|https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0158173&type=printable|Drought Land-Cover NPP Three-North MODIS"
)

# ------------------------------------------------------------------
# Downloader
# ------------------------------------------------------------------
success_list=()
skip_list=()
fail_list=()

download_one() {
  local category="$1" filename="$2" url="$3" title="$4"
  local target="$ROOT/$category/$filename"

  if [[ -s "$target" ]] && head -c 4 "$target" | grep -q '%PDF'; then
    echo "[skip]  $category/$filename (already present)" | tee -a "$LOG"
    skip_list+=("$category|$filename|$url|$title")
    return
  fi

  echo "[fetch] $category/$filename" | tee -a "$LOG"
  # -f: fail on HTTP errors, -L: follow redirects, -s: silent, --max-time: cap
  curl -fL -s --max-time "$TIMEOUT" -A "$UA" -o "$target" "$url" 2>>"$LOG"
  local rc=$?

  if [[ $rc -ne 0 ]] || [[ ! -s "$target" ]]; then
    echo "[FAIL]  $category/$filename (curl rc=$rc)" | tee -a "$LOG"
    rm -f "$target"
    fail_list+=("$category|$filename|$url|$title|curl_rc_$rc")
    return
  fi

  # Verify %PDF magic; if HTML or other, discard.
  if ! head -c 4 "$target" | grep -q '%PDF'; then
    local ctype
    ctype=$(file -b --mime-type "$target" 2>/dev/null || echo unknown)
    echo "[FAIL]  $category/$filename (not PDF, got $ctype)" | tee -a "$LOG"
    rm -f "$target"
    fail_list+=("$category|$filename|$url|$title|not_pdf_$ctype")
    return
  fi

  local size
  size=$(wc -c <"$target" | tr -d ' ')
  echo "[ok]    $category/$filename ($size bytes)" | tee -a "$LOG"
  success_list+=("$category|$filename|$url|$title|$size")
}

# Download sequentially to stay polite to publisher servers.
for entry in "${entries[@]}"; do
  IFS='|' read -r cat fname url title <<<"$entry"
  download_one "$cat" "$fname" "$url" "$title"
  sleep 1
done

# ------------------------------------------------------------------
# Manifest (JSON)
# ------------------------------------------------------------------
json_escape() { python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1"; }

total_ok=${#success_list[@]}
total_skip=${#skip_list[@]}
total_fail=${#fail_list[@]}

# Compute total bytes across successes + skips
total_bytes=0
for entry in "${success_list[@]}"; do
  size="${entry##*|}"
  total_bytes=$((total_bytes + size))
done
for entry in "${skip_list[@]}"; do
  IFS='|' read -r cat fname _url _title <<<"$entry"
  if [[ -s "$ROOT/$cat/$fname" ]]; then
    s=$(wc -c <"$ROOT/$cat/$fname" | tr -d ' ')
    total_bytes=$((total_bytes + s))
  fi
done

{
  echo "{"
  echo "  \"generated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"total_downloaded\": $total_ok,"
  echo "  \"total_skipped_existing\": $total_skip,"
  echo "  \"total_failed\": $total_fail,"
  echo "  \"total_bytes\": $total_bytes,"
  echo "  \"documents\": ["
  first=1
  for entry in "${success_list[@]}" "${skip_list[@]}"; do
    IFS='|' read -r cat fname url title rest <<<"$entry"
    size_field=""
    if [[ -s "$ROOT/$cat/$fname" ]]; then
      s=$(wc -c <"$ROOT/$cat/$fname" | tr -d ' ')
      size_field=", \"size_bytes\": $s"
    fi
    if [[ $first -eq 0 ]]; then echo ","; fi
    first=0
    printf '    {"category": %s, "filename": %s, "path": %s, "title": %s, "source_url": %s%s}' \
      "$(json_escape "$cat")" \
      "$(json_escape "$fname")" \
      "$(json_escape "$cat/$fname")" \
      "$(json_escape "$title")" \
      "$(json_escape "$url")" \
      "$size_field"
  done
  echo ""
  echo "  ],"
  echo "  \"failed\": ["
  first=1
  for entry in "${fail_list[@]}"; do
    IFS='|' read -r cat fname url title reason <<<"$entry"
    if [[ $first -eq 0 ]]; then echo ","; fi
    first=0
    printf '    {"category": %s, "filename": %s, "source_url": %s, "title": %s, "reason": %s}' \
      "$(json_escape "$cat")" \
      "$(json_escape "$fname")" \
      "$(json_escape "$url")" \
      "$(json_escape "$title")" \
      "$(json_escape "$reason")"
  done
  echo ""
  echo "  ]"
  echo "}"
} >"$MANIFEST"

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
echo "==================== Summary ===================="
echo "Downloaded: $total_ok"
echo "Already had: $total_skip"
echo "Failed: $total_fail"
printf "Total corpus size: %.2f MB\n" "$(echo "scale=2; $total_bytes/1048576" | bc)"
echo "Manifest: $MANIFEST"
echo "Log:      $LOG"
echo ""
if [[ $total_fail -gt 0 ]]; then
  echo "Failed URLs (report these to Claude for a second pass):"
  for entry in "${fail_list[@]}"; do
    IFS='|' read -r cat fname url title reason <<<"$entry"
    echo "  - [$reason] $cat/$fname  <$url>"
  done
fi
