PYTHON ?= python3

# -------- Shared paths/config --------
DATA_ROOT ?= ./results_5k
OUT_DIR ?= ./visuals
TIMING_CSV ?= ./timing_summary.csv
CORRECTNESS_REPORT ?= ./results_5k/compare_mpi_vs_serial_t1000.txt

# -------- Heatmap defaults (override on command line) --------
IMPL ?= mpi
RUN_TAG ?= n5000_p8_t50_100_500_1000
MATRIX ?= mpi_out_t50.txt
INITIAL ?= input_5000.txt
OUTPUTS ?= mpi_out_t100.txt mpi_out_t500.txt mpi_out_t1000.txt
ARTIFACT_PREFIX ?= fig5_mpi_n5000_p8_t50_100_500_1000
FRAME_CACHE_DIR ?= ./visuals/$(ARTIFACT_PREFIX)_frames
MAX_DIM ?= 133
FPS ?= 1.25

PLOT_SCRIPT = ./plot_timing_figures.py
HEATMAP_SCRIPT = ./plot_heatmaps_gif.py

.PHONY: help all plots heatmaps \
	plots-both plots-stacked plots-unstacked \
	heatmap-band heatmap-4frames heatmap-gif heatmap-all

help:
	@echo "Usage examples:"
	@echo "  make plots                       # both stacked + unstacked fig1/fig2"
	@echo "  make plots-stacked               # stacked only"
	@echo "  make plots-unstacked             # unstacked only"
	@echo "  make heatmap-band                # band-only heatmap"
	@echo "  make heatmap-4frames             # export frame PNGs (no GIF)"
	@echo "  make heatmap-gif                 # GIF only (resume-capable frame cache)"
	@echo "  make heatmap-all                 # band + frame PNGs + GIF"
	@echo "  make all                         # plots + heatmap-all"
	@echo ""
	@echo "Override variables as needed:"
	@echo "  make heatmap-gif IMPL=mpi RUN_TAG=n5000_p8_t50_1000_step50 \\"
	@echo "       MATRIX=mpi_out_t50.txt OUTPUTS='mpi_out_t100.txt mpi_out_t150.txt ...'"

all: plots heatmap-all

# -------- Timing plots --------
plots: plots-both

plots-both:
	$(PYTHON) "$(PLOT_SCRIPT)" --fig12-layout both

plots-stacked:
	$(PYTHON) "$(PLOT_SCRIPT)" --fig12-layout stacked

plots-unstacked:
	$(PYTHON) "$(PLOT_SCRIPT)" --fig12-layout unstacked

# -------- Heatmap command base --------
HEATMAP_BASE = $(PYTHON) "$(HEATMAP_SCRIPT)" \
	--data-root "$(DATA_ROOT)" \
	--impl "$(IMPL)" \
	--run-tag "$(RUN_TAG)" \
	--matrix "$(MATRIX)" \
	--initial "$(INITIAL)" \
	--outputs $(OUTPUTS) \
	--artifact-prefix "$(ARTIFACT_PREFIX)" \
	--timing-csv "$(TIMING_CSV)" \
	--correctness-report "$(CORRECTNESS_REPORT)" \
	--out-dir "$(OUT_DIR)" \
	--norm-mode linear \
	--max-dim $(MAX_DIM) \
	--fps $(FPS)

# -------- Heatmap only targets --------
heatmaps: heatmap-all

heatmap-band:
	$(HEATMAP_BASE) --band-zoom

heatmap-4frames:
	$(HEATMAP_BASE) --export-frame-pngs

heatmap-gif:
	$(HEATMAP_BASE) --enable-gif --frame-cache-dir "$(FRAME_CACHE_DIR)" --resume-frames

heatmap-all:
	$(HEATMAP_BASE) --band-zoom --export-frame-pngs --enable-gif --frame-cache-dir "$(FRAME_CACHE_DIR)" --resume-frames
