# E1R execution implementation amendment

The preregistered scientific design, seeds, metrics, conditions, selection policy and hypothesis rules are unchanged. The first sequential pilot attempt was stopped before result serialization after the progress monitor reported rule 32 at 165.1 s. The successor uses multiprocessing across independent rule IDs. Executor.map preserves rule order. A representative rule is recomputed sequentially and in a spawned worker; continuation requires byte-identical output.
