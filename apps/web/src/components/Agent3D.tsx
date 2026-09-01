"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { Text } from "@react-three/drei";
import { AgentCard } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  IDLE: "#94a3b8", // slate-400
  WORKING: "#10b981", // emerald-500
  COMMUNICATING: "#3b82f6", // blue-500
  WAITING: "#f59e0b", // amber-500
  APPROVAL_REQUIRED: "#f59e0b", // amber-500
  BLOCKED: "#ef4444", // red-500
  COMPLETED: "#10b981", // emerald-500
};

export function Agent3D({
  agent,
  status,
  selected,
  position,
  onClick,
}: {
  agent: AgentCard;
  status: string;
  selected: boolean;
  position: [number, number, number];
  onClick: () => void;
}) {
  const group = useRef<THREE.Group>(null);
  const characterRef = useRef<THREE.Group>(null);
  const screenRef = useRef<THREE.Mesh>(null);
  const alertRef = useRef<THREE.Mesh>(null);

  const baseColor = STATUS_COLOR[status] ?? "#94a3b8";
  const screenColor = useMemo(() => new THREE.Color(baseColor), [baseColor]);
  
  // Handle hover state
  const [hovered, setHovered] = (require("react") as any).useState(false);

  useFrame((state) => {
    if (!group.current || !characterRef.current) return;

    const t = state.clock.getElapsedTime();
    const isAlert = status === "APPROVAL_REQUIRED" || status === "BLOCKED";
    const isActive = status === "WORKING" || status === "COMMUNICATING";

    // Character typing animation (bobbing)
    if (isActive) {
      characterRef.current.position.y = Math.sin(t * 15) * 0.02;
      characterRef.current.rotation.y = Math.sin(t * 5) * 0.1;
    } else {
      characterRef.current.position.y = 0;
      characterRef.current.rotation.y = Math.sin(t * 2) * 0.05;
    }

    // Screen glow
    if (screenRef.current) {
      const material = screenRef.current.material as THREE.MeshStandardMaterial;
      if (isAlert) {
        material.emissiveIntensity = 0.5 + (Math.sin(t * 8) + 1) / 2 * 0.5;
      } else if (isActive) {
        material.emissiveIntensity = 0.8 + (Math.sin(t * 4) + 1) / 2 * 0.4;
      } else {
        material.emissiveIntensity = 0.2;
      }
    }

    // Alert symbol bounce
    if (alertRef.current && isAlert) {
      alertRef.current.position.y = 1.8 + Math.abs(Math.sin(t * 5)) * 0.2;
      alertRef.current.rotation.y = t * 2;
    }
  });

  return (
    <group
      ref={group}
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        setHovered(false);
        document.body.style.cursor = "auto";
      }}
    >
      {/* --- DESK --- */}
      {/* Desk Top */}
      <mesh position={[0, 0.75, -0.2]} castShadow receiveShadow>
        <boxGeometry args={[1.4, 0.05, 0.8]} />
        <meshStandardMaterial color="#d97706" roughness={0.7} /> {/* Wooden desk */}
      </mesh>
      {/* Desk Legs */}
      <mesh position={[-0.65, 0.375, -0.5]} castShadow receiveShadow>
        <boxGeometry args={[0.05, 0.75, 0.05]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} />
      </mesh>
      <mesh position={[0.65, 0.375, -0.5]} castShadow receiveShadow>
        <boxGeometry args={[0.05, 0.75, 0.05]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} />
      </mesh>
      <mesh position={[-0.65, 0.375, 0.1]} castShadow receiveShadow>
        <boxGeometry args={[0.05, 0.75, 0.05]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} />
      </mesh>
      <mesh position={[0.65, 0.375, 0.1]} castShadow receiveShadow>
        <boxGeometry args={[0.05, 0.75, 0.05]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} />
      </mesh>

      {/* --- COMPUTER MONITOR --- */}
      {/* Monitor Base */}
      <mesh position={[0, 0.85, -0.4]} castShadow>
        <boxGeometry args={[0.1, 0.2, 0.1]} />
        <meshStandardMaterial color="#1e293b" />
      </mesh>
      {/* Monitor Screen Frame */}
      <mesh position={[0, 1.0, -0.35]} castShadow>
        <boxGeometry args={[0.7, 0.45, 0.05]} />
        <meshStandardMaterial color="#1e293b" />
      </mesh>
      {/* Screen (Glows based on status) */}
      <mesh ref={screenRef} position={[0, 1.0, -0.32]}>
        <planeGeometry args={[0.65, 0.4]} />
        <meshStandardMaterial color={screenColor} emissive={screenColor} emissiveIntensity={0.5} />
      </mesh>

      {/* --- CHAIR --- */}
      <mesh position={[0, 0.25, 0.3]} castShadow>
        <cylinderGeometry args={[0.2, 0.2, 0.5, 16]} />
        <meshStandardMaterial color="#334155" />
      </mesh>
      <mesh position={[0, 0.5, 0.3]} castShadow>
        <boxGeometry args={[0.4, 0.05, 0.4]} />
        <meshStandardMaterial color="#1e293b" />
      </mesh>
      <mesh position={[0, 0.7, 0.45]} castShadow>
        <boxGeometry args={[0.4, 0.4, 0.05]} />
        <meshStandardMaterial color="#1e293b" />
      </mesh>

      {/* --- CHARACTER --- */}
      <group ref={characterRef} position={[0, 0, 0]}>
        {/* Torso */}
        <mesh position={[0, 0.7, 0.25]} castShadow>
          <boxGeometry args={[0.3, 0.4, 0.2]} />
          <meshStandardMaterial color="#3b82f6" roughness={0.9} /> {/* Blue shirt */}
        </mesh>
        {/* Head */}
        <mesh position={[0, 1.0, 0.25]} castShadow>
          <sphereGeometry args={[0.15, 16, 16]} />
          <meshStandardMaterial color="#fcd34d" roughness={0.6} /> {/* Skin tone */}
        </mesh>
        {/* Arms (Resting on desk) */}
        <mesh position={[-0.2, 0.75, 0.1]} rotation={[Math.PI / 4, 0, 0]} castShadow>
          <cylinderGeometry args={[0.04, 0.04, 0.3]} />
          <meshStandardMaterial color="#3b82f6" />
        </mesh>
        <mesh position={[0.2, 0.75, 0.1]} rotation={[Math.PI / 4, 0, 0]} castShadow>
          <cylinderGeometry args={[0.04, 0.04, 0.3]} />
          <meshStandardMaterial color="#3b82f6" />
        </mesh>
      </group>

      {/* --- SELECTION RING --- */}
      {(selected || hovered) && (
        <mesh position={[0, 0.02, 0.1]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.6, 0.7, 32]} />
          <meshBasicMaterial color="#3b82f6" opacity={0.6} transparent side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* --- NAMEPLATE --- */}
      <Text
        position={[0, 1.3, -0.3]}
        fontSize={0.15}
        color="#1e293b"
        anchorX="center"
        anchorY="middle"
      >
        {agent.name.split(" ")[0]}
      </Text>

      {/* --- ALERT / STATUS SYMBOL --- */}
      {(status === "APPROVAL_REQUIRED" || status === "BLOCKED") && (
        <mesh ref={alertRef} position={[0, 1.8, 0]}>
          {/* Exclamation point using a cylinder and a sphere */}
          <group>
            <mesh position={[0, 0.15, 0]}>
              <cylinderGeometry args={[0.05, 0.02, 0.2, 8]} />
              <meshStandardMaterial color={screenColor} emissive={screenColor} emissiveIntensity={1} />
            </mesh>
            <mesh position={[0, -0.05, 0]}>
              <sphereGeometry args={[0.04, 8, 8]} />
              <meshStandardMaterial color={screenColor} emissive={screenColor} emissiveIntensity={1} />
            </mesh>
          </group>
        </mesh>
      )}
    </group>
  );
}
