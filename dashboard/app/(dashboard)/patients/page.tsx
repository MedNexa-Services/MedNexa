"use client";

import * as React from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { searchPatients, type PatientOut } from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { describePatient, formatDateTime } from "@/lib/format";
import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/pagination";
import { PatientFormDialog } from "@/components/patients/PatientFormDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const PAGE_SIZE = 20;
export default function PatientsPage() {
  const { hospitalId } = useHospital();
  const [search, setSearch] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [page, setPage] = React.useState(0);
  const [patients, setPatients] = React.useState<PatientOut[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [formOpen, setFormOpen] = React.useState(false);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = React.useCallback(async () => {
    if (!hospitalId) return;
    const byPhone = /^[+\d][\d\s-]*$/.test(query);
    try {
      const res = await searchPatients({
        hospital_id: hospitalId,
        phone: query && byPhone ? query : undefined,
        name: query && !byPhone ? query : undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setPatients(res.items);
      setTotal(res.total);
    } catch (err) {
      if (byPhone) {
        setPatients([]);
        setTotal(0);
      } else {
        toast.error(err instanceof Error ? err.message : "Patients could not be loaded.");
      }
    } finally {
      setLoading(false);
    }
  }, [hospitalId, query, page]);

  React.useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Patients"
        description="Everyone who has booked, at the desk or by phone. One phone number can belong to several patients."
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus /> Add patient
          </Button>
        }
      />

      <div className="relative mb-4 max-w-sm">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label="Search patients"
          placeholder="Name or full phone number"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-8 bg-card pl-8"
        />
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-card">
        {loading ? (
          <div className="h-72 animate-pulse" />
        ) : patients.length === 0 ? (
          <div className="px-6 py-10">
            <p className="text-sm font-semibold">{query ? "No patients match" : "No patients yet"}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {query
                ? "Search by part of the name, or by the full 10-digit phone number."
                : "Patients are added automatically when they book."}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Name</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Age and gender</TableHead>
                <TableHead>Registered</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {patients.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>
                    <Link href={`/patients/${p.id}`} className="font-medium hover:underline">
                      {p.name}
                    </Link>
                  </TableCell>
                  <TableCell>{p.phone}</TableCell>
                  <TableCell className="text-muted-foreground">{describePatient(p) || "Not given"}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(p.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
      </div>

      <PatientFormDialog open={formOpen} onOpenChange={setFormOpen} onSuccess={load} />
    </>
  );
}
