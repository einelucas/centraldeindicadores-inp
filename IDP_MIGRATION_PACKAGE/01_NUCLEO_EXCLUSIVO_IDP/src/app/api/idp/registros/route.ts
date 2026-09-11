import { NextRequest, NextResponse } from "next/server";
import type { Prisma } from "@prisma/client";
import { z } from "zod";
import { recalcIdpIndicators } from "@/features/idp/services";
import {
  formatPeriodRangeLabel,
  normalizePeriodRange,
  parsePeriodRangeParams,
  periodRangeWhere,
} from "@/lib/period";
import { recordAudit } from "@/server/audit";
import { requirePermission } from "@/server/auth/session";
import { prisma } from "@/server/database/prisma";
import { handleApiError } from "@/server/http";

const REFERENCE_FIELDS = { year: "referenceYear", month: "referenceMonth" };

/**
 * GET /api/idp/registros — contagem de RSOs para um período (ou toda a base,
 * sem período). Usado pela tela de exclusão para mostrar quantos registros
 * serão apagados antes de confirmar.
 */
export async function GET(req: NextRequest) {
  try {
    await requirePermission("indicators:edit");
    const { searchParams } = new URL(req.url);
    const period = parsePeriodRangeParams(searchParams);
    const where = period
      ? (periodRangeWhere(period, REFERENCE_FIELDS) as Prisma.IdpRsoRecordWhereInput)
      : {};
    const count = await prisma.idpRsoRecord.count({ where });
    return NextResponse.json({ count });
  } catch (error) {
    return handleApiError(error);
  }
}

const deleteSchema = z.union([
  z.object({ all: z.literal(true) }),
  z.object({
    periodStartYear: z.number().int().min(2000).max(2200),
    periodStartMonth: z.number().int().min(1).max(12),
    periodEndYear: z.number().int().min(2000).max(2200),
    periodEndMonth: z.number().int().min(1).max(12),
  }),
]);

/**
 * DELETE /api/idp/registros — limpa o histórico administrativo de RSOs, todo
 * ou apenas um período específico (só ADMIN); publicação permanece.
 */
export async function DELETE(req: NextRequest) {
  try {
    const user = await requirePermission("indicators:edit");
    const body = deleteSchema.parse(await req.json());

    if ("all" in body) {
      const count = await prisma.idpRsoRecord.count();
      if (count === 0) return NextResponse.json({ ok: true, deleted: 0 });

      await prisma.$transaction(async (tx) => {
        await tx.idpRsoRecord.deleteMany();
        await tx.indicatorResult.deleteMany({ where: { module: "idp" } });
      });

      await recordAudit({
        userId: user.id,
        action: "RECORDS_CLEARED",
        entity: "IdpRsoRecord",
        previousData: { quantidade: count },
        metadata: { module: "idp", escopo: "todos_rsos" },
      });

      return NextResponse.json({ ok: true, deleted: count });
    }

    const range = normalizePeriodRange({
      startYear: body.periodStartYear,
      startMonth: body.periodStartMonth,
      endYear: body.periodEndYear,
      endMonth: body.periodEndMonth,
    });
    const where = periodRangeWhere(range, REFERENCE_FIELDS) as Prisma.IdpRsoRecordWhereInput;
    const count = await prisma.idpRsoRecord.count({ where });
    if (count === 0) return NextResponse.json({ ok: true, deleted: 0 });

    await prisma.$transaction(
      async (tx) => {
        await tx.idpRsoRecord.deleteMany({ where });
        await recalcIdpIndicators(tx);
      },
      { maxWait: 10_000, timeout: 60_000 },
    );

    await recordAudit({
      userId: user.id,
      action: "RECORDS_CLEARED",
      entity: "IdpRsoRecord",
      previousData: { quantidade: count },
      metadata: { module: "idp", escopo: "periodo", periodo: formatPeriodRangeLabel(range) },
    });

    return NextResponse.json({ ok: true, deleted: count });
  } catch (error) {
    return handleApiError(error);
  }
}
