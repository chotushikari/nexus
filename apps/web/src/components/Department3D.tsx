"use client";

import { useMemo } from "react";
import * as THREE from "three";
import { Text } from "@react-three/drei";
import { AgentCard } from "@/lib/api";
import { Agent3D } from "./Agent3D";

interface Department {
  id: string;
  name: string;
  icon: string;
  description: string;
  color: string;
  agents: string[];
}

export function Department3D({
  dept,
  agents,
  agentStatus,
  selectedAgentId,
  onSelectAgent,
  position,
  size,
}: {
  dept: Department;
  agents: AgentCard[];
  agentStatus: Record<string, string>;
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
  position: [number, number, number];
  size: [number, number];
}) {
  const deptAgents = agents.filter((a) => dept.agents.includes(a.id));

  // Department signature color for accent lines on the walls
  const colorObj = useMemo(() => new THREE.Color(dept.color), [dept.color]);

  const wallHeight = 1.2;
  const wallThickness = 0.2;
  const w = size[0];
  const d = size[1];

  return (
    <group position={position}>
      {/* Carpet / Floor Area */}
      <mesh position={[0, 0, 0]} receiveShadow>
        <boxGeometry args={[w - 0.1, 0.05, d - 0.1]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.8} />
      </mesh>

      {/* Back Wall */}
      <mesh position={[0, wallHeight / 2, -d / 2 + wallThickness / 2]} castShadow receiveShadow>
        <boxGeometry args={[w, wallHeight, wallThickness]} />
        <meshStandardMaterial color="#ffffff" roughness={0.9} />
      </mesh>
      {/* Accent stripe on back wall */}
      <mesh position={[0, wallHeight - 0.1, -d / 2 + wallThickness / 2 + 0.01]}>
        <boxGeometry args={[w + 0.02, 0.05, wallThickness + 0.02]} />
        <meshStandardMaterial color={colorObj} />
      </mesh>

      {/* Left Wall */}
      <mesh position={[-w / 2 + wallThickness / 2, wallHeight / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[wallThickness, wallHeight, d]} />
        <meshStandardMaterial color="#ffffff" roughness={0.9} />
      </mesh>
      
      {/* Right Wall (Partial / Entryway) */}
      <mesh position={[w / 2 - wallThickness / 2, wallHeight / 2, -d / 4]} castShadow receiveShadow>
        <boxGeometry args={[wallThickness, wallHeight, d / 2]} />
        <meshStandardMaterial color="#ffffff" roughness={0.9} />
      </mesh>

      {/* Department Name Signage */}
      <group position={[-w / 2 + 0.5, wallHeight, -d / 2 + 0.3]}>
        <Text
          position={[0, 0, 0]}
          fontSize={0.4}
          color="#1e293b"
          anchorX="left"
          anchorY="bottom"
          font="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hjp-Ek-_EeA.woff"
        >
          {dept.icon} {dept.name}
        </Text>
      </group>

      {/* Agents / Desks */}
      {deptAgents.map((agent, i) => {
        // Arrange desks in a grid within the department
        const cols = Math.floor(w / 3); // More space per desk
        const r = Math.floor(i / cols);
        const c = i % cols;
        const xOffset = -w / 2 + 1.5 + c * 3;
        const zOffset = -d / 2 + 2 + r * 3;

        return (
          <Agent3D
            key={agent.id}
            agent={agent}
            status={agentStatus[agent.id] ?? "IDLE"}
            selected={selectedAgentId === agent.id}
            position={[xOffset, 0, zOffset]}
            onClick={() => onSelectAgent(agent.id)}
          />
        );
      })}
    </group>
  );
}
