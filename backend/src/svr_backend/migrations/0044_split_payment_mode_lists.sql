-- Section 5's Payment Mode and Section 6's Payment Mode are not the same
-- question, and sharing one list put the wrong options in front of each
-- (client, 2026-09-26):
--
--   "here, if there is a payment mode it's a credit so I don't need cash in
--    phone pay and credit card... I don't have to see those three list of
--    values" (Section 5 - Today New Credit(s))
--   "Section 6... you don't have to show the credit CR within the brackets.
--    I don't need that drop down list of value" (Section 6 - Old/Pending
--    Credit Received)
--
-- 0041/0043 put all four values in one 'payment_modes' list on the theory that
-- "how was this money handled" was one question asked at both ends of a
-- credit's life. It is not: Section 5 records a credit being ISSUED, which by
-- definition has no cash/card mode yet - that only exists once it is
-- COLLECTED, in Section 6. Sharing the list meant Section 5 offered three
-- options that never apply there, and Section 6 offered one that never
-- applies there.
--
-- Split into two lists. 'payment_modes' (Section 6) keeps Cash / Phone Pay /
-- Credit Card and loses Credit (CR). A new 'credit_payment_modes' (Section 5)
-- holds just Credit (CR) - a real dropdown, not a fixed label, so the "+ New"
-- pattern still applies if the station ever records a New Credit some other
-- way.

DELETE FROM trial_balance_option WHERE list_key = 'payment_modes' AND value = 'Credit (CR)';

INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('credit_payment_modes', 'Credit (CR)', 1, 'client-2026-09-26');
