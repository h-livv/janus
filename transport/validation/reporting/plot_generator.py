"""Plot generation driven by metric plot payloads."""

import os

import matplotlib.pyplot as plt
import numpy as np


class PlotGenerator:
    def __init__(self, output_dir: str, case_name: str):
        self.case_name = case_name.lower().replace("validation", "")
        self.output_dir = os.path.join(output_dir, self.case_name)
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(self, plot_payloads: list[dict]):
        conservation_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "conservation"]
        error_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "error"]
        convergence_payloads = [p for p in plot_payloads if p and p.get("plot_type") == "convergence"]

        if conservation_payloads:
            self._plot_conservation(conservation_payloads[0])
        if error_payloads:
            self._plot_error(error_payloads[0])
        for cp in convergence_payloads:
            self._plot_convergence(cp)

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
        dts = payload["dts"]
        errors = payload["errors"]
        slope = payload.get("slope", 0.0)
        log_dts = np.log10(dts)
        log_errors = np.log10(errors)
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(log_dts, log_errors, marker="o", color="darkorange", linewidth=2,
                label=f"Boris Step Error (Slope = {slope:.2f})")
        ax.set_xlabel("log(Timestep dt)")
        ax.set_ylabel("log(Error)")
        ax.set_title(payload.get("title", "Timestep Convergence"))
        textstr = f"Convergence Slope: {slope:.2f}"
        props = dict(boxstyle="round", facecolor="wheat", alpha=0.5)
        ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=10,
                verticalalignment="top", bbox=props)
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
        ax.legend(loc="lower right")
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "timestep_convergence.png"), dpi=150)
        plt.close()
