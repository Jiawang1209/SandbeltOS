#!/usr/bin/env bash
# download_corpus_round2.sh — Second-pass fixes + additional sources.
#
# Re-attempts Round-1 failures with publisher-specific strategies and adds
# ~10 new papers from reliable OA publishers.
#
# Usage:
#   bash backend/rag/download_corpus_round2.sh

set -u

ROOT="$(cd "$(dirname "$0")/docs" && pwd)"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT=60
LOG="$ROOT/download_round2.log"
MANIFEST="$ROOT/manifest_round2.json"

mkdir -p "$ROOT/gov" "$ROOT/papers_cn" "$ROOT/papers_en"
: >"$LOG"

# ------------------------------------------------------------------
# Entries — CATEGORY|FILENAME|URL|TITLE|STRATEGY
# Strategies: mdpi | govcn | default
# ------------------------------------------------------------------
entries=(
  # ---------- gov.cn retries (relax TLS) ----------
  "gov|three-north-development-report-1978-2018.pdf|https://www.forestry.gov.cn/html/sbj/sbj_5102/20220125154748720366588/file/20220419084114310665949.pdf|三北防护林体系建设发展报告（1978-2018）|govcn"
  "gov|three-north-monitoring-indicators.pdf|https://www.forestry.gov.cn/html/sbj/sbj_5283/20200421113148624935210/file/20200421113210094462687.pdf|三北防护林体系建设监测评价指标研究|govcn"

  # ---------- MDPI retries with compressed + referer ----------
  "papers_en|2023_li_otindag_desertification_30yr.pdf|https://www.mdpi.com/2072-4292/15/1/279/pdf|Desertification Otindag Sandy Land 30yr|mdpi"
  "papers_en|2024_wang_three-north_npp_2decades.pdf|https://www.mdpi.com/2071-1050/16/9/3656/pdf|Three-North Shelter Forest NPP Two Decades|mdpi"
  "papers_en|2021_forest-changes_precipitation-zones_three-north.pdf|https://www.mdpi.com/2072-4292/13/4/543/pdf|Forest Changes by Precipitation Zones Three-North|mdpi"
  "papers_en|2022_vegetation_ecological_quality_three-north.pdf|https://www.mdpi.com/2072-4292/14/22/5708/pdf|Vegetation Ecological Quality Three-North 2000-2020|mdpi"
  "papers_en|2022_landuse_vegetation_three-north_2000-2020.pdf|https://www.mdpi.com/2071-1050/14/24/16489/pdf|Land Use Vegetation Three-North 2000-2020|mdpi"
  "papers_en|2024_hunshandake_vegetation_degradation_risk.pdf|https://www.mdpi.com/2073-4441/16/16/2258/pdf|Vegetation Degradation Risk Hunshandake Sandy Land|mdpi"
  "papers_en|2025_wind_erosion_inner_mongolia_1990-2022.pdf|https://www.mdpi.com/2072-4292/17/14/2365/pdf|Soil Wind Erosion Inner Mongolia 1990-2022|mdpi"
  "papers_en|2025_wind_erosion_aral_rweq_gee.pdf|https://www.mdpi.com/2072-4292/17/16/2788/pdf|Wind Erosion Aral Sea RWEQ GEE|mdpi"
  "papers_en|2019_wind_erosion_semiarid_sandy_inner_mongolia.pdf|https://www.mdpi.com/2071-1050/11/1/188/pdf|Wind Erosion Semi-Arid Sandy Inner Mongolia|mdpi"
  "papers_en|2020_soil_wind_erosion_central_asia_gee.pdf|https://www.mdpi.com/2072-4292/12/20/3430/pdf|Soil Wind Erosion Central Asia GEE|mdpi"
  "papers_en|2021_horqin_land_vegetation.pdf|https://www.mdpi.com/2073-445X/10/1/80/pdf|Horqin Sandy Land Vegetation|mdpi"
  "papers_en|2022_ulmus_caragana_transpiration_bashang.pdf|https://www.mdpi.com/1999-4907/13/7/1081/pdf|Ulmus Caragana Transpiration Bashang|mdpi"

  # ---------- New reliable sources (Nature / Frontiers / PLOS / Copernicus / SpringerOpen) ----------
  "papers_en|2023_sand_dune_vegetation_succession_mu_us.pdf|https://www.nature.com/articles/s41598-023-46167-z.pdf|Vegetation Succession Mu Us Sand Dunes|default"
  "papers_en|2022_grassland_vegetation_inner_mongolia_climate.pdf|https://www.nature.com/articles/s41598-022-26482-7.pdf|Grassland Vegetation Inner Mongolia Climate|default"
  "papers_en|2021_soil_carbon_shelterbelt_northern_china.pdf|https://www.nature.com/articles/s41598-021-00020-3.pdf|Soil Carbon Shelterbelt Northern China|default"
  "papers_en|2023_ndvi_dynamic_semi_arid_grassland.pdf|https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2023.1157995/pdf|NDVI Dynamics Semi-Arid Grassland|default"
  "papers_en|2022_ecosystem_service_arid_china.pdf|https://www.frontiersin.org/journals/environmental-science/articles/10.3389/fenvs.2022.996138/pdf|Ecosystem Services Arid China|default"
  "papers_en|2024_drought_vegetation_three_north_monitoring.pdf|https://www.frontiersin.org/journals/forests-and-global-change/articles/10.3389/ffgc.2024.1367848/pdf|Drought Vegetation Three-North Monitoring|default"
  "papers_en|2020_wind_erosion_modeling_gobi.pdf|https://esd.copernicus.org/articles/11/833/2020/esd-11-833-2020.pdf|Wind Erosion Modeling Gobi Desert|default"
  "papers_en|2023_land_cover_change_sandy_lands_china.pdf|https://bg.copernicus.org/articles/20/4591/2023/bg-20-4591-2023.pdf|Land Cover Change Sandy Lands China|default"
  "papers_en|2021_dryland_vegetation_greening_china.pdf|https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0254424&type=printable|Dryland Vegetation Greening China|default"
  "papers_en|2024_carbon_sequestration_shelterbelt_china.pdf|https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0301214&type=printable|Carbon Sequestration Shelterbelt China|default"
)

# ------------------------------------------------------------------
# Downloader with per-strategy args
# ------------------------------------------------------------------
success_list=()
skip_list=()
fail_list=()

curl_args_for() {
  local strategy="$1" url="$2"
  case "$strategy" in
    mdpi)
      # MDPI blocks bare curl; mimic browser with compressed + referer + Accept.
      echo "--compressed --http1.1 -H Referer:_https://www.mdpi.com/ -H Accept:_application/pdf,text/html,*/* -H Accept-Language:_en-US,en;q=0.9"
      ;;
    govcn)
      # gov.cn has old ciphers; relax TLS, allow self-signed, http/1.1.
      echo "-k --tls-max 1.2 --ciphers DEFAULT@SECLEVEL=0 --http1.1"
      ;;
    *)
      echo ""
      ;;
  esac
}

download_one() {
  local category="$1" filename="$2" url="$3" title="$4" strategy="$5"
  local target="$ROOT/$category/$filename"

  if [[ -s "$target" ]] && head -c 4 "$target" | grep -q '%PDF'; then
    echo "[skip]  $category/$filename (already present)" | tee -a "$LOG"
    skip_list+=("$category|$filename")
    return
  fi

  echo "[fetch] [$strategy] $category/$filename" | tee -a "$LOG"

  # Build curl command per strategy. Use bash arrays to handle headers cleanly.
  local -a extra_args=()
  case "$strategy" in
    mdpi)
      extra_args=(
        --compressed --http1.1
        -H "Referer: https://www.mdpi.com/"
        -H "Accept: application/pdf,text/html;q=0.9,*/*;q=0.8"
        -H "Accept-Language: en-US,en;q=0.9"
        -H "Sec-Fetch-Dest: document"
        -H "Sec-Fetch-Mode: navigate"
      )
      ;;
    govcn)
      extra_args=(
        -k --http1.1
        --tls-max 1.2
        --ciphers "DEFAULT@SECLEVEL=0"
      )
      ;;
  esac

  curl -fL -s --max-time "$TIMEOUT" -A "$UA" "${extra_args[@]}" -o "$target" "$url" 2>>"$LOG"
  local rc=$?

  if [[ $rc -ne 0 ]] || [[ ! -s "$target" ]]; then
    echo "[FAIL]  $category/$filename (curl rc=$rc)" | tee -a "$LOG"
    rm -f "$target"
    fail_list+=("$category|$filename|$url|rc_$rc")
    return
  fi

  if ! head -c 4 "$target" | grep -q '%PDF'; then
    local ctype
    ctype=$(file -b --mime-type "$target" 2>/dev/null || echo unknown)
    echo "[FAIL]  $category/$filename (not PDF, $ctype)" | tee -a "$LOG"
    rm -f "$target"
    fail_list+=("$category|$filename|$url|not_pdf_$ctype")
    return
  fi

  local size
  size=$(wc -c <"$target" | tr -d ' ')
  echo "[ok]    $category/$filename ($size bytes)" | tee -a "$LOG"
  success_list+=("$category|$filename|$size")
}

for entry in "${entries[@]}"; do
  IFS='|' read -r cat fname url title strat <<<"$entry"
  download_one "$cat" "$fname" "$url" "$title" "$strat"
  sleep 1
done

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
echo "==================== Round-2 Summary ===================="
echo "Newly downloaded: ${#success_list[@]}"
echo "Already present:  ${#skip_list[@]}"
echo "Still failing:    ${#fail_list[@]}"
echo ""
if [[ ${#fail_list[@]} -gt 0 ]]; then
  echo "Still-failing URLs:"
  for entry in "${fail_list[@]}"; do
    IFS='|' read -r cat fname url reason <<<"$entry"
    echo "  - [$reason] $cat/$fname  <$url>"
  done
fi
echo ""
echo "Log: $LOG"

# Final corpus tally
total_pdfs=$(find "$ROOT" -name "*.pdf" -type f | wc -l | tr -d ' ')
total_size=$(find "$ROOT" -name "*.pdf" -type f -exec wc -c {} \; | awk '{s+=$1} END {print s}')
printf "\nTotal corpus: %d PDFs, %.2f MB\n" "$total_pdfs" "$(echo "scale=2; $total_size/1048576" | bc)"
