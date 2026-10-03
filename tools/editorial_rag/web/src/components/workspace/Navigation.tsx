import * as Tabs from '@radix-ui/react-tabs';
import { MessageSquare, ListChecks, Columns2, PanelLeftClose, Send } from 'lucide-react';
import { Sidebar, SidebarContent, SidebarHeader, SidebarFooter, SidebarMenuButton, useSidebar } from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';

const sections = [
  { value: 'real', label: 'Responder conversación', icon: MessageSquare },
  { value: 'advanced', label: 'Revisión avanzada', icon: ListChecks },
  { value: 'followup', label: 'Seguimientos ManyChat', icon: Send },
  { value: 'synthetic', label: 'Comparador sintético', icon: Columns2 },
];
export function Navigation({ mode }: { mode: string }) {
  const { isMobile, setOpenMobile } = useSidebar();
  return <Sidebar collapsible="icon" variant="floating" className="workspace-sidebar">
    <SidebarHeader><div className="workspace-brand"><span className="brand-mark">T</span><span className="nav-label">TATO <small>ESPACIO EDITORIAL</small></span></div></SidebarHeader>
    <SidebarContent>
      <Tabs.List aria-label="Modo de trabajo" className="workspace-navigation">
        {sections.map(({ value, label, icon: Icon }) => <SidebarMenuButton key={value} asChild isActive={mode === value} title={label}>
          <Tabs.Trigger value={value} onClick={() => { if (isMobile) setOpenMobile(false); }}>
            <Icon aria-hidden="true" /><span className="nav-label">{label}</span>
          </Tabs.Trigger>
        </SidebarMenuButton>)}
      </Tabs.List>
    </SidebarContent>
    <SidebarFooter>
      {isMobile && <Button variant="outline" onClick={() => setOpenMobile(false)}><PanelLeftClose aria-hidden="true" />Cerrar navegación</Button>}
    </SidebarFooter>
  </Sidebar>;
}
