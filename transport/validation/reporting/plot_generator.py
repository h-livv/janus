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
        transmission_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "transmission"]
        loss_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "loss"]

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
        if transmission_payloads:
            self._plot_transmission(transmission_payloads[0])
        if loss_payloads:
            self._plot_loss(loss_payloads[0])

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
        errors = [max(e, 1e-30) for e in payload["errors"]]
        log_dts = np.log10(dts)
        log_errors = np.log10(errors)
        show_slope = payload.get("show_slope", True)
        slope = payload.get("slope", 0.0)
        label = (
            f"Boris Step Error (Slope = {slope:.2f})"
            if show_slope
            else "Exit error vs Timestep dt"
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
        ax.grid(True, linestyle="--", alpha=0.5)
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
