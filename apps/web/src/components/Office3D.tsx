"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls, Environment, ContactShadows } from "@react-three/drei";
import { AgentCard } from "@/lib/api";
import { Department3D } from "./Department3D";
import * as THREE from "three";

interface Department {
  id: string;
  name: string;
  icon: string;
  description: string;
  color: string;
  agents: string[];
}

export function Office3D({
  departments,
  agents,
  agentStatus,
  selectedAgentId,
  onSelectAgent,
}: {
  departments: Department[];
  agents: AgentCard[];
  agentStatus: Record<string, string>;
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
}) {
  const cols = 2;
  const margin = 2;
  const deptWidth = 10;
  const deptDepth = 8;

  return (
    <div className="w-full h-full absolute inset-0 bg-[#f1f5f9]">
      <Canvas
        camera={{ position: [20, 20, 20], fov: 35, near: 0.1, far: 1000 }}
        shadows
        gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
      >
        <color attach="background" args={["#f1f5f9"]} />
        <fog attach="fog" args={["#f1f5f9", 30, 80]} />

        {/* Realistic Office Lighting */}
        <ambientLight intensity={0.7} color="#ffffff" />
        <directionalLight
          position={[15, 25, 10]}
          intensity={1.2}
          color="#fdfbf7"
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-left={-25}
          shadow-camera-right={25}
          shadow-camera-top={25}
          shadow-camera-bottom={-25}
          shadow-bias={-0.0001}
        />
        
        {/* Soft fill light from opposite side */}
        <directionalLight position={[-15, 15, -15]} intensity={0.4} color="#e0f2fe" />

        {/* Concrete/Tile Floor Base */}
        <mesh position={[0, -0.05, 0]} receiveShadow>
          <planeGeometry args={[200, 200]} />
          <meshStandardMaterial color="#e2e8f0" roughness={0.9} />
        </mesh>

        {/* Office Tile Grid */}
        <gridHelper args={[200, 100, "#cbd5e1", "#cbd5e1"]} position={[0, -0.04, 0]} />

        {/* Departments Layout */}
        <group position={[-(cols * deptWidth) / 2 + deptWidth / 2, 0, -deptDepth]}>
          {departments.map((dept, i) => {
            const r = Math.floor(i / cols);
            const c = i % cols;
            const x = c * (deptWidth + margin);
            const z = r * (deptDepth + margin);

            return (
              <Department3D
                key={dept.id}
                dept={dept}
                agents={agents}
                agentStatus={agentStatus}
                selectedAgentId={selectedAgentId}
                onSelectAgent={onSelectAgent}
                position={[x, 0, z]}
                size={[deptWidth, deptDepth]}
              />
            );
          })}
        </group>

        {/* Camera Controls */}
        <OrbitControls
          makeDefault
          minPolarAngle={0}
          maxPolarAngle={Math.PI / 2.2}
          minDistance={10}
          maxDistance={60}
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          target={[0, 0, 0]}
        />
        
        <ContactShadows position={[0, -0.04, 0]} opacity={0.3} scale={50} blur={1} far={4} color="#0f172a" />
        <Environment preset="apartment" />
      </Canvas>
    </div>
  );
}
