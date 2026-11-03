"""Plot generation driven by metric plot payloads."""

import os

import matplotlib.pyplot as plt
import numpy as np

from transport.validation.reporting.lattice_annotations import uses_longitudinal_position


class PlotGenerator:
    def __init__(self, output_dir: str, case_name: str):
        self.case_name = case_name.lower().replace("validation", "")
        self.output_dir = os.path.join(output_dir, self.case_name)
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def _disable_offset_notation(ax):
        for axis_name in ("x", "y"):
            axis = getattr(ax, f"{axis_name}axis")
            fmt = axis.get_major_formatter()
            if hasattr(fmt, "set_useOffset"):
                fmt.set_useOffset(False)
            if axis_name == "x" or ax.get_yscale() == "linear":
                ax.ticklabel_format(axis=axis_name, useOffset=False)

    def generate(self, plot_payloads: list[dict]):
        conservation_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "conservation"]
        error_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "error"]
        convergence_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "convergence"]
        envelope_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "envelope"]
        emittance_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "emittance"]
        geometric_emittance_payloads = [
            p for p in plot_payloads if p and p.get("plot_type") == "geometric_emittance"
        ]
        transmission_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "transmission"]
        loss_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "loss"]
        rms_size_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "rms_size"]
        divergence_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "divergence"]
        phase_space_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "phase_space"]
        momentum_spread_payloads = [
            p for p in plot_payloads if p and p.get("plot_type") == "momentum_spread"
        ]
        element_loss_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "element_loss"]
        transfer_matrix_payloads = [
            p for p in plot_payloads if p and p.get("plot_type") == "transfer_matrix"
        ]
        envelope_cmp_payloads = [
            p for p in plot_payloads if p and p.get("plot_type") == "envelope_comparison"
        ]
        twiss_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "twiss"]
        twiss_cmp_payloads = [
            p for p in plot_payloads if p and p.get("plot_type") == "twiss_comparison"
        ]
        radius_sweep_payloads = [
            p for p in plot_payloads if p and p.get("plot_type") == "horn_radius_sweep"
        ]

        if conservation_payloads:
            self._plot_conservation(conservation_payloads[0])
        if error_payloads:
            self._plot_error(error_payloads[0])
        for cp in convergence_payloads:
            self._plot_convergence(cp)
        if envelope_payloads:
            self._plot_envelope(envelope_payloads[0])
        for ep in emittance_payloads:
            self._plot_emittance(ep)
        if geometric_emittance_payloads:
            self._plot_curve_panel(geometric_emittance_payloads[0], "geometric_emittance.png")
        if transmission_payloads:
            self._plot_transmission(transmission_payloads[0])
        if loss_payloads:
            self._plot_loss(loss_payloads[0])
        if rms_size_payloads:
            self._plot_curve_panel(rms_size_payloads[0], "rms_size.png")
        if divergence_payloads:
            self._plot_curve_panel(divergence_payloads[0], "divergence.png")
        if phase_space_payloads:
            self._plot_phase_space(phase_space_payloads[0])
        if momentum_spread_payloads:
            self._plot_momentum_spread(momentum_spread_payloads[0])
        if element_loss_payloads:
            self._plot_element_loss(element_loss_payloads[0])
        if transfer_matrix_payloads:
            self._plot_transfer_matrix(transfer_matrix_payloads[0])
        if envelope_cmp_payloads:
            self._plot_curve_panel(envelope_cmp_payloads[0], "envelope_comparison.png")
        for tp in twiss_payloads:
            self._plot_twiss(tp)
        for tcp in twiss_cmp_payloads:
            self._plot_twiss_comparison(tcp)
        for rp in radius_sweep_payloads:
            self._plot_horn_radius_sweep(rp)

    def _plot_conservation(self, payload: dict):
        fig, ax = plt.subplots(figsize=(8, 5))
        for curve in payload.get("curves", []):
            ax.plot(
                curve["x"], curve["y"],
                label=curve.get("label"), color=curve.get("color", "blue"),
                linestyle=curve.get("linestyle", "-"), alpha=0.8,
            )
        if payload.get("log_y"):
            ax.set_yscale("log")
        ax.set_xlabel(payload.get("xlabel", "Time (ns)"))
        ax.set_ylabel(payload.get("ylabel", "Relative Drift"))
        ax.set_title(payload.get("title", "Conservation"))
        if uses_longitudinal_position(payload):
            self._annotate_lattice_elements(ax, payload)
        self._disable_offset_notation(ax)
        ax.legend()
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "conservation.png"), dpi=150)
        plt.close()

    def _plot_error(self, payload: dict):
        curves = payload.get("curves", [])
        if not curves:
            return
        fig, ax = plt.subplots(figsize=(8, 5))
        for curve in curves:
            ax.plot(curve["x"], curve["y"], label=curve.get("label"), color=curve.get("color"))
        ax.set_xlabel(payload.get("xlabel", "Time (ns)"))
        ax.set_ylabel(payload.get("ylabel", "Error"))
        ax.set_title(payload.get("title", "Error vs Time"))
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "error.png"), dpi=150)
        plt.close()

    def _plot_convergence(self, payload: dict):
        if payload.get("plot_scale") == "linear":
            self._plot_convergence_linear(payload)
            return

        dts = payload["dts"]
        errors = [max(e, 1e-15) for e in payload["errors"]]
        log_dts = np.log10(dts)
        log_errors = np.log10(errors)
        show_slope = payload.get("show_slope", True)
        slope = payload.get("slope", 0.0)
        label = (
            f"Boris Step Error (Slope = {slope:.2f})"
            if show_slope
            else "Exit error vs log(Timestep dt)"
        )
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(
            log_dts,
            log_errors,
            marker="o",
            color="darkorange",
            linewidth=2,
            label=label,
        )
        ax.set_xlabel("log(Timestep dt)")
        ax.set_ylabel("log(Error)")
        ax.set_title(payload.get("title", "Timestep Refinement"))
        if show_slope:
            textstr = f"Convergence Slope: {slope:.2f}"
            props = dict(boxstyle="round", facecolor="wheat", alpha=0.5)
            ax.text(
                0.05,
                0.95,
                textstr,
                transform=ax.transAxes,
                fontsize=10,
                verticalalignment="top",
                bbox=props,
            )
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
        ax.legend(loc="lower right")
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "timestep_convergence.png"), dpi=150)
        plt.close()

    def _plot_convergence_linear(self, payload: dict):
        dts = payload["dts"]
        errors = payload["errors"]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(
            dts,
            errors,
            marker="o",
            color="darkorange",
            linewidth=2,
            label="Exit error vs finest grid",
        )
        ax.set_xlabel("Timestep dt (s)")
        ax.set_ylabel("Error (m)")
        ax.set_title(payload.get("title", "Timestep Refinement"))
        self._disable_offset_notation(ax)
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
        ax.legend(loc="best")
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "timestep_convergence.png"), dpi=150)
        plt.close()

    @staticmethod
    def _annotate_lattice_elements(ax, payload: dict):
        elements = payload.get("lattice_elements")
        if not elements:
            return
        for i, el in enumerate(elements):
            if i > 0:
                ax.axvline(
                    el["z_start"],
                    color="0.45",
                    linestyle="--",
                    linewidth=1.0,
                    alpha=0.85,
                    zorder=1,
                )
        ymin, ymax = ax.get_ylim()
        y_pad = (ymax - ymin) * 0.04 if ymax > ymin else 0.0
        y_text = ymax - y_pad
        for el in elements:
            z_mid = 0.5 * (el["z_start"] + el["z_end"])
            ax.text(
                z_mid,
                y_text,
                el["label"],
                ha="center",
                va="top",
                fontsize=8,
                color="0.3",
                clip_on=True,
            )

    def _plot_curve_panel(self, payload: dict, filename: str):
        curves = payload.get("curves", [])
        if not curves:
            return
        fig, ax = plt.subplots(figsize=(8, 5))
        for curve in curves:
            ax.plot(
                curve["x"],
                curve["y"],
                label=curve.get("label"),
                color=curve.get("color"),
                linestyle=curve.get("linestyle", "-"),
                alpha=0.85,
                zorder=2,
            )
        ax.set_xlabel(payload.get("xlabel", ""))
        ax.set_ylabel(payload.get("ylabel", ""))
        ax.set_title(payload.get("title", ""))
        if uses_longitudinal_position(payload):
            self._annotate_lattice_elements(ax, payload)
        self._disable_offset_notation(ax)
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, filename), dpi=150)
        plt.close()

    def _plot_envelope(self, payload: dict):
        self._plot_curve_panel(payload, "envelope.png")

    def _plot_emittance(self, payload: dict):
        plane = "horizontal" if "Horizontal" in payload.get("title", "") else "vertical"
        self._plot_curve_panel(payload, f"emittance_{plane}.png")

    def _plot_transmission(self, payload: dict):
        self._plot_curve_panel(payload, "transmission.png")

    def _plot_loss(self, payload: dict):
        self._plot_curve_panel(payload, "loss.png")

    def _plot_phase_space(self, payload: dict):
        panels = payload.get("panels", [])
        if not panels:
            return
        fig, axes = plt.subplots(1, len(panels), figsize=(4.2 * len(panels), 4.2))
        if len(panels) == 1:
            axes = [axes]
        for ax, panel in zip(axes, panels):
            for series in panel.get("series", []):
                x = np.asarray(series.get("x", []))
                y = np.asarray(series.get("y", []))
                if len(x) == 0:
                    continue
                ax.scatter(
                    x,
                    y,
                    s=12,
                    alpha=0.7,
                    label=series.get("label"),
                    color=series.get("color"),
                )
            ax.set_xlabel(panel.get("xlabel", ""))
            ax.set_ylabel(panel.get("ylabel", ""))
            ax.set_title(panel.get("title", ""))
            ax.grid(True, linestyle="--", alpha=0.5)
            ax.legend(loc="best", fontsize=8)
            self._disable_offset_notation(ax)
        fig.suptitle(payload.get("title", "Phase Space"))
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "phase_space.png"), dpi=150)
        plt.close()

    def _plot_momentum_spread(self, payload: dict):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

        ax = axes[0]
        for curve in payload.get("curves", []):
            ax.plot(
                curve["x"],
                curve["y"],
                label=curve.get("label"),
                color=curve.get("color"),
                linestyle=curve.get("linestyle", "-"),
                alpha=0.85,
            )
        ax.set_xlabel("Longitudinal Position z (m)")
        ax.set_ylabel("Relative")
        ax.set_title("Δp/p along lattice")
        if uses_longitudinal_position(payload):
            self._annotate_lattice_elements(ax, payload)
        ax.legend(fontsize=8)
        ax.grid(True, linestyle="--", alpha=0.5)
        self._disable_offset_notation(ax)

        ax = axes[1]
        for hist in payload.get("histograms", []):
            values = np.asarray(hist.get("values", []), dtype=np.float64)
            if len(values) == 0:
                continue
            ax.hist(
                values,
                bins=min(40, max(10, len(values) // 2)),
                alpha=0.55,
                label=hist.get("label"),
                color=hist.get("color"),
            )
        ax.set_xlabel(r"Δp/p")
        ax.set_ylabel("Counts")
        ax.set_title(
            "Entrance / exit histograms\n"
            f"RMS_in={payload.get('dpp_rms_in', 0):.3e}, "
            f"RMS_out={payload.get('dpp_rms_out', 0):.3e}"
        )
        ax.legend(fontsize=8)
        ax.grid(True, linestyle="--", alpha=0.5)
        self._disable_offset_notation(ax)

        fig.suptitle(payload.get("title", "Momentum Spread"))
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "momentum_spread.png"), dpi=150)
        plt.close()

    def _plot_element_loss(self, payload: dict):
        labels = payload.get("labels", [])
        losses = np.asarray(payload.get("losses", []), dtype=np.float64)
        cum_tx = np.asarray(payload.get("cumulative_transmission", []), dtype=np.float64)
        if len(labels) == 0:
            return

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        x = np.arange(len(labels))

        ax = axes[0]
        ax.bar(x, losses, color="crimson", alpha=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("Particles lost")
        ax.set_title("Losses per element")
        ax.grid(True, axis="y", linestyle="--", alpha=0.5)

        ax = axes[1]
        ax.plot(x, cum_tx, "o-", color="green", label="Cumulative transmission")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("N_alive / N_initial")
        ax.set_ylim(0.0, 1.05)
        ax.set_title(f"Cumulative transmission (N₀={payload.get('n_initial', 0)})")
        ax.legend(fontsize=8)
        ax.grid(True, linestyle="--", alpha=0.5)

        fig.suptitle(payload.get("title", "Acceptance Losses"))
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "element_losses.png"), dpi=150)
        plt.close()

    def _plot_transfer_matrix(self, payload: dict):
        R_num = np.asarray(payload.get("R_numerical"))
        R_ref = np.asarray(payload.get("R_reference"))
        diff = np.asarray(payload.get("diff"))
        if R_num.size == 0 or R_ref.size == 0:
            return

        fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
        panels = [
            (R_num, "Numerical R"),
            (R_ref, f"{payload.get('backend', 'ref')} R"),
            (diff, "Difference"),
        ]
        for ax, (mat, title) in zip(axes, panels):
            im = ax.imshow(mat, cmap="coolwarm", aspect="equal")
            ax.set_title(title)
            ax.set_xticks(range(4))
            ax.set_yticks(range(4))
            ax.set_xticklabels(["x", "x'", "y", "y'"])
            ax.set_yticklabels(["x", "x'", "y", "y'"])
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.suptitle(
            payload.get("title", "Transfer Matrix")
            + f"\n‖ΔR‖_F / ‖R‖_F = {payload.get('frobenius_relative', float('nan')):.3e}"
        )
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "transfer_matrix.png"), dpi=150)
        plt.close()

    def _plot_twiss(self, payload: dict):
        elements = payload.get("lattice_elements")
        for fig_spec in payload.get("figures", []):
            curves = fig_spec.get("curves", [])
            if not curves:
                continue
            fig, ax = plt.subplots(figsize=(8, 5))
            for curve in curves:
                ax.plot(
                    curve["x"],
                    curve["y"],
                    label=curve.get("label"),
                    color=curve.get("color"),
                    linestyle=curve.get("linestyle", "-"),
                    alpha=0.85,
                    zorder=2,
                )
            ax.set_xlabel("Longitudinal Position z (m)")
            ax.set_ylabel(fig_spec.get("ylabel", ""))
            ax.set_title(fig_spec.get("title", payload.get("title", "Twiss")))
            panel = {"lattice_elements": elements, "xlabel": "Longitudinal Position z (m)"}
            if uses_longitudinal_position(panel):
                self._annotate_lattice_elements(ax, panel)
            self._disable_offset_notation(ax)
            ax.legend()
            ax.grid(True, linestyle="--", alpha=0.5)
            plt.tight_layout()
            filename = fig_spec.get("filename", "twiss.png")
            plt.savefig(os.path.join(self.output_dir, filename), dpi=150)
            plt.close()

    def _plot_twiss_comparison(self, payload: dict):
        filename = payload.get("filename", f"twiss_{payload.get('family', 'cmp')}_comparison.png")
        fig, ax = plt.subplots(figsize=(8, 5))
        for curve in payload.get("curves", []):
            ax.plot(
                curve["x"],
                curve["y"],
                label=curve.get("label"),
                color=curve.get("color"),
                linestyle=curve.get("linestyle", "-"),
                alpha=0.85,
                zorder=2,
            )
        ax.set_xlabel(payload.get("xlabel", "Longitudinal Position z (m)"))
        ax.set_ylabel(payload.get("ylabel", ""))
        ax.set_title(payload.get("title", "Twiss Comparison"))
        if uses_longitudinal_position(payload):
            self._annotate_lattice_elements(ax, payload)

        errors = payload.get("errors") or {}
        text = (
            f"RMS rel={errors.get('rms_relative', float('nan')):.3e}\n"
            f"max |Δ|={errors.get('max_absolute', float('nan')):.3e}\n"
            f"max rel={errors.get('max_relative', float('nan')):.3e}"
        )
        ax.text(
            0.02,
            0.98,
            text,
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=8,
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )
        self._disable_offset_notation(ax)
        ax.legend(fontsize=8)
        ax.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, filename), dpi=150)
        plt.close()

    def _plot_horn_radius_sweep(self, payload: dict):
        inv_r = np.asarray(payload["inv_r"], dtype=np.float64)
        delta_pr = np.asarray(payload["delta_pr"], dtype=np.float64)
        delta_pr_fit = np.asarray(payload["delta_pr_fit"], dtype=np.float64)
        radii = np.asarray(payload["radii"], dtype=np.float64)
        product = np.asarray(payload["product"], dtype=np.float64)
        a_fit = float(payload.get("fit_slope", 0.0))
        resid = float(payload.get("residual_rms_relative", 0.0))

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

        ax = axes[0]
        ax.plot(inv_r, delta_pr, "o", color="C0", label="Simulated Δp_r")
        order = np.argsort(inv_r)
        ax.plot(
            inv_r[order],
            delta_pr_fit[order],
            "-",
            color="C3",
            label=f"Fit Δp_r = a/r (a={a_fit:.4g})",
        )
        ax.set_xlabel("1/r (1/m)")
        ax.set_ylabel("Δp_r (MeV/c)")
        ax.set_title("Δp_r vs 1/r")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="best")
        self._disable_offset_notation(ax)

        ax = axes[1]
        ax.plot(radii, product, "o-", color="C2", label="Δp_r · r")
        ax.axhline(a_fit, color="C3", linestyle="--", label="Fit constant a")
        ax.set_xlabel("r (m)")
        ax.set_ylabel("Δp_r · r (MeV/c · m)")
        ax.set_title(f"Constancy of Δp_r · r (rel. RMS={resid:.2e})")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="best")
        self._disable_offset_notation(ax)

        fig.suptitle(payload.get("title", "Radial Momentum Kick vs. 1/r"))
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "horn_radius_sweep.png"), dpi=150)
        plt.close()
