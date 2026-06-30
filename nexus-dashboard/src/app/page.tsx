"use client";

import React, { useState } from "react";
import {
	Activity,
	Cpu,
	Network,
	Server,
	Zap,
	Terminal,
	Send,
} from "lucide-react";

export default function Dashboard() {
	// Real Telemetry State
	const [traffic, setTraffic] = useState(0);
	const [latency, setLatency] = useState(0);
	const [activeRoute, setActiveRoute] = useState("IDLE");

	// Real Execution State
	const [prompt, setPrompt] = useState("");
	const [output, setOutput] = useState("Awaiting command...");
	const [isExecuting, setIsExecuting] = useState(false);

	const [trustVerdict, setTrustVerdict] = useState("");

	const fireExecution = async () => {
		if (!prompt) return;
		setIsExecuting(true);
		setTraffic((prev) => prev + 1); // Track the request
		setOutput("Executing across gRPC cluster...");

		try {
			const res = await fetch("http://127.0.0.1:8080/api/v1/chat", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ user_id: "nexus_ui", prompt: prompt }),
			});

			const data = await res.json();

			// UPDATE UI WITH REAL METRICS FROM RUST!
			setLatency(data.gateway_latency_ms.toFixed(2));
			setActiveRoute(data.source);
			setOutput(data.final_output);

			if (data.status && data.status.includes("trust=")) {
				const match = data.status.match(/verdict=(\w+)/);
				if (match) setTrustVerdict(match[1]);
			} else {
				setTrustVerdict("");
			}
		} catch (err) {
			setOutput(
				"🚨 Cluster Connection Failed. Ensure Rust (8080), Router (8001), and Swarm (8002) are running.",
			);
		} finally {
			setIsExecuting(false);
		}
	};

	return (
		<div className="min-h-screen bg-[#09090b] text-gray-100 p-8 font-sans selection:bg-indigo-500/30">
			{/* HEADER */}
			<header className="flex justify-between items-end border-b border-gray-800 pb-6 mb-8">
				<div>
					<h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">
						AetherOS Telemetry
					</h1>
					<p className="text-xl text-indigo-400 font-medium">
						Live cluster telemetry
					</p>
				</div>
				<div className="flex items-center gap-3 bg-green-500/10 px-4 py-2 rounded-full border border-green-500/20">
					<div className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
					<span className="text-green-400 text-sm font-semibold tracking-wide uppercase">
						Cluster Online
					</span>
				</div>
			</header>

			{/* TOP METRICS ROW */}
			<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
				<MetricCard
					title="Total gRPC Traffic"
					value={`${traffic} reqs`}
					icon={<Network size={20} />}
					trend="Live"
				/>
				<MetricCard
					title="Last Execution Latency"
					value={`${latency} ms`}
					icon={<Zap size={20} />}
					trend={activeRoute}
				/>
			</div>

			{/* LIVE EXECUTION TERMINAL */}
			<div className="bg-[#121214] border border-gray-800 rounded-xl overflow-hidden mb-8 shadow-2xl">
				<div className="bg-[#1a1a1e] border-b border-gray-800 p-4 flex items-center gap-2">
					<Terminal size={18} className="text-gray-400" />
					<h2 className="text-sm font-bold tracking-widest text-gray-400 uppercase">
						Master Execution Terminal
					</h2>
				</div>
				<div className="p-6">
					<div className="flex gap-4 mb-6">
						<input
							type="text"
							value={prompt}
							onChange={(e) => setPrompt(e.target.value)}
							onKeyDown={(e) => e.key === "Enter" && fireExecution()}
							placeholder="e.g., 'Deploy a highly scalable kubernetes cluster'"
							className="flex-1 bg-[#09090b] border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition-colors"
						/>
						<button
							onClick={fireExecution}
							disabled={isExecuting}
							className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-lg font-bold flex items-center gap-2 transition-all disabled:opacity-50"
						>
							{isExecuting ? "Routing..." : "Execute"} <Send size={16} />
						</button>
					</div>
					<div className="bg-[#09090b] rounded-lg p-4 font-mono text-sm text-green-400 min-h-[120px] max-h-[400px] overflow-y-auto whitespace-pre-wrap border border-gray-800/50 shadow-inner">
						{output}
					</div>
				</div>
			</div>

			<h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
				<Server className="text-gray-400" /> Live Node Status
			</h2>
			<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
				<NodeCard
					name="Rust API Gateway"
					port="TCP : 8080"
					status={isExecuting ? "Routing" : "Healthy"}
					type="L1 Router & HTTP/2 Ingress"
					cpu={isExecuting ? "Active" : "Idle"}
					ram="~40–60 MB"
					color="border-orange-500/30"
					glow={
						isExecuting
							? "shadow-[0_0_40px_rgba(249,115,22,0.15)]"
							: "shadow-[0_0_30px_rgba(249,115,22,0.05)]"
					}
				/>

				<NodeCard
					name="Semantic ML Router"
					port="gRPC : 8001"
					status={isExecuting ? "Calculating" : "Healthy"}
					type="Vector Math & Classification"
					cpu={isExecuting ? "Active" : "Idle"}
					ram="~800 MB–1.2 GB"
					color="border-blue-500/30"
					glow={
						isExecuting
							? "shadow-[0_0_40px_rgba(59,130,246,0.15)]"
							: "shadow-[0_0_30px_rgba(59,130,246,0.05)]"
					}
				/>

				<NodeCard
					name="Cognitive AI Swarm"
					port="gRPC : 8002"
					status={isExecuting ? "Executing" : "Idle"}
					type="Multi-Agent Orchestration"
					cpu={isExecuting ? "Active" : "Idle"}
					ram="~1.5–2.5 GB"
					color="border-indigo-500/30"
					glow={
						isExecuting
							? "shadow-[0_0_40px_rgba(99,102,241,0.15)]"
							: "shadow-[0_0_30px_rgba(99,102,241,0.05)]"
					}
				/>
			</div>
		</div>
	);
}

// --- UI COMPONENTS ---

function MetricCard({
	title,
	value,
	icon,
	trend,
}: {
	title: string;
	value: string | number;
	icon: React.ReactNode;
	trend?: string;
}) {
	return (
		<div className="bg-[#121214] border border-gray-800 rounded-xl p-6 shadow-sm">
			<div className="flex justify-between items-start mb-4">
				<h3 className="text-gray-400 text-sm font-medium">{title}</h3>
				<div className="text-gray-500 bg-gray-800/50 p-2 rounded-lg">
					{icon}
				</div>
			</div>
			<div className="flex items-baseline gap-3">
				<span className="text-3xl font-bold text-white tracking-tight">
					{value}
				</span>
				{trend && (
					<span
						className={`text-sm font-medium ${trend === "COGNITIVE_SWARM" ? "text-indigo-400" : trend === "LOCAL_FAST_LLM" ? "text-blue-400" : "text-green-400"}`}
					>
						{trend}
					</span>
				)}
			</div>
		</div>
	);
}

function NodeCard({ name, port, status, type, cpu, ram, color, glow }: any) {
	const isBusy = status !== "Healthy" && status !== "Idle";
	return (
		<div
			className={`bg-[#121214] border ${color} ${glow} rounded-xl p-6 relative overflow-hidden transition-all duration-300`}
		>
			<div className="flex justify-between items-start mb-6">
				<div>
					<h3 className="text-xl font-bold text-white mb-1">{name}</h3>
					<p className="text-sm text-gray-400 font-mono">{port}</p>
				</div>
				<div
					className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-2 ${isBusy ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30" : "bg-green-500/10 text-green-400 border border-green-500/20"}`}
				>
					{isBusy && <Activity size={12} className="animate-pulse" />}
					{status}
				</div>
			</div>

			<div className="space-y-4">
				<div>
					<div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
						Architecture
					</div>
					<div className="text-sm text-gray-200">{type}</div>
				</div>

				<div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-800/50">
					<div>
						<div className="text-xs flex items-center gap-1 text-gray-500 uppercase tracking-wider mb-1">
							<Cpu size={12} /> CPU Load
						</div>
						<div className="text-lg font-mono text-white transition-all duration-300">
							{cpu}
						</div>
					</div>
					<div>
						<div className="text-xs flex items-center gap-1 text-gray-500 uppercase tracking-wider mb-1">
							<Server size={12} /> Memory
						</div>
						<div className="text-lg font-mono text-white">{ram}</div>
					</div>
				</div>
			</div>
		</div>
	);
}
