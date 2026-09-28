import SwiftUI

enum FormValue: Codable {
    case string(String)
    case bool(Bool)
    case date(String)
    case number(Double)

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .date(let value):
            try container.encode(value)
        case .number(let value):
            try container.encode(value)
        }
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let stringValue = try? container.decode(String.self) {
            self = .string(stringValue)
        } else if let boolValue = try? container.decode(Bool.self) {
            self = .bool(boolValue)
        } else if let doubleValue = try? container.decode(Double.self) {
            self = .number(doubleValue)
        } else {
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Cannot decode FormValue"
            )
        }
    }
}

struct SchemaFormView: View {
    let category: LogCategory
    @Binding var input: String
    @Binding var formData: [String: FormValue]
    let onSubmit: () -> Void
    @State private var errorMessage: String?
    let isLoading: Bool
    
    // Validate all required fields including conditional ones
    private func validateForm() -> Bool {
        guard let schema = category.formSchema else {
            return !input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
        
        let missingFields = findMissingRequiredFields(fields: schema.fields, formData: formData)
        if !missingFields.isEmpty {
            errorMessage = "Please fill out all required fields"
            return false
        }
        
        // Special validation for visitor_log: time_out must be after time_in
        if category.key == "visitor_log" {
            if let timeInValue = formData["time_in"], let timeOutValue = formData["time_out"],
               case .date(let timeInStr) = timeInValue, case .date(let timeOutStr) = timeOutValue {
                
                let formatter = ISO8601DateFormatter()
                if let timeIn = formatter.date(from: timeInStr),
                   let timeOut = formatter.date(from: timeOutStr) {
                    if timeOut <= timeIn {
                        errorMessage = "Time Out must be after Time In"
                        return false
                    }
                }
            }
        }
        
        errorMessage = nil
        return true
    }
    
    // Recursively check for missing required fields
    private func findMissingRequiredFields(fields: [FormField], formData: [String: FormValue]) -> [String] {
        var missing: [String] = []
        
        for field in fields {
            // Check if this field is required and missing
            if field.required {
                if let value = formData[field.id] {
                    // For text fields, check if non-empty
                    if case .string(let s) = value, s.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        missing.append(field.label)
                    }
                } else {
                    missing.append(field.label)
                }
            }
            
            // Check child fields if parent is "Yes"
            if let childFields = field.childFields,
               let parentValue = formData[field.id] {
                if case .string(let s) = parentValue, s == "Yes" {
                    missing.append(contentsOf: findMissingRequiredFields(fields: childFields, formData: formData))
                }
            }
        }
        
        return missing
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let schema = category.formSchema {
                FormFieldsView(
                    fields: schema.fields,
                    formData: $formData,
                    errorMessage: $errorMessage
                )
            } else {
                // Fallback: simple text input
                ZStack(alignment: .topLeading) {
                    RoundedRectangle(cornerRadius: 16)
                        .fill(Color.white)
                        .frame(minHeight: 140)

                    TextEditor(text: $input)
                        .padding(12)
                        .frame(minHeight: 140)
                        .background(Color.clear)
                        .cornerRadius(16)
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(Color.gray.opacity(0.3), lineWidth: 1)
                        )
                        .overlay(
                            Group {
                                if input.isEmpty {
                                    Text("Enter notes...")
                                        .foregroundColor(.gray)
                                        .padding(.horizontal, 16)
                                        .padding(.vertical, 14)
                                }
                            }, alignment: .topLeading
                        )
                }
            }

            if let errorMessage = errorMessage {
                Text(errorMessage)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundColor(.red)
            }

            HStack {
                Spacer()
                Button {
                    if validateForm() {
                        onSubmit()
                    }
                } label: {
                    Text("Save Entry")
                        .font(.system(size: 16, weight: .semibold))
                        .padding(.vertical, 10)
                        .padding(.horizontal, 16)
                        .background(Color("AccentColor"))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
                .disabled(isLoading)
            }
        }
    }
}

struct FormFieldsView: View {
    let fields: [FormField]
    @Binding var formData: [String: FormValue]
    @Binding var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(fields) { field in
                FormFieldView(
                    field: field,
                    formData: $formData,
                    errorMessage: $errorMessage
                )
            }
        }
    }
}

struct FormFieldView: View {
    let field: FormField
    @Binding var formData: [String: FormValue]
    @Binding var errorMessage: String?
    @State private var dateValue = Date()
    @State private var textValue = ""
    @State private var yesNoValue: Bool?
    
    // Watch for formData changes to reset local state
    private var shouldReset: Bool {
        formData[field.id] == nil
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if(field.label != "Details") {
                Text(field.label)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color("DefaultTextColor"))
            }
            

            switch field.type {
            case "text":
                ZStack(alignment: .topLeading) {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.white)
                        .frame(minHeight: 80)

                    TextEditor(text: $textValue)
                        .padding(12)
                        .frame(minHeight: 80)
                        .background(Color.clear)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.gray.opacity(0.3), lineWidth: 1)
                        )
                        .overlay(
                            Group {
                                if textValue.isEmpty {
                                    Text("Please explain")
                                        .font(.system(size: 15, weight: .medium))
                                        .foregroundColor(.gray)
                                        .padding(.horizontal, 16)
                                        .padding(.vertical, 22)
                                }
                            }, alignment: .topLeading
                        )
                        .onChange(of: textValue) { _, newValue in
                            formData[field.id] = .string(newValue)
                        }
                        .onChange(of: shouldReset) { _, reset in
                            if reset {
                                textValue = ""
                            }
                        }
                }

            case "yesno":
                HStack(spacing: 12) {
                    Button(action: {
                        yesNoValue = true
                        formData[field.id] = .string("Yes")
                    }) {
                        Text("Yes")
                            .font(.system(size: 15, weight: .medium))
                            .foregroundColor(Color("DefaultTextColor"))
                            .frame(maxWidth: .infinity)
                            .frame(height: 30)
                            .background(yesNoValue == true ? Color("SelectedButton") : Color("UnselectedButton"))
                            .cornerRadius(20)
                    }

                    Button(action: {
                        yesNoValue = false
                        formData[field.id] = .string("No")
                        // Clear child field values when "No" is selected
                        if let childFields = field.childFields {
                            clearChildFields(childFields)
                        }
                    }) {
                        Text("No")
                            .font(.system(size: 15, weight: .medium))
                            .foregroundColor(Color("DefaultTextColor"))
                            .frame(maxWidth: .infinity)
                            .frame(height: 30)
                            .background(yesNoValue == false ? Color("SelectedButton") : Color("UnselectedButton"))
                            .cornerRadius(20)
                    }
                }
                .onChange(of: shouldReset) { _, reset in
                    if reset {
                        yesNoValue = nil
                    }
                }

                // Show child fields if "Yes" is selected
                if let childFields = field.childFields, yesNoValue == true {
                    VStack(alignment: .leading, spacing: 12) {
                        Divider().padding(.vertical, 4)
                        FormFieldsView(
                            fields: childFields,
                            formData: $formData,
                            errorMessage: $errorMessage
                        )
                    }
                    .padding(.leading, 16)
                }

            case "datetime":
                VStack(spacing: 12) {
                    if field.fieldType == "date" || field.fieldType == "both" {
                        DatePicker(
                            "Date",
                            selection: $dateValue,
                            displayedComponents: .date
                        )
                        .datePickerStyle(.compact)
                        .onChange(of: dateValue) { _, _ in
                            formData[field.id] = .date(dateValue.ISO8601Format())
                        }
                    }

                    if field.fieldType == "time" || field.fieldType == "both" {
                        DatePicker(
                            "Time",
                            selection: $dateValue,
                            displayedComponents: .hourAndMinute
                        )
                        .onChange(of: dateValue) { _, _ in
                            formData[field.id] = .date(dateValue.ISO8601Format())
                        }
                    }
                }
                .padding(12)
                .background(Color.white)
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.gray.opacity(0.3), lineWidth: 1)
                )
                .onChange(of: shouldReset) { _, reset in
                    if reset {
                        dateValue = Date()
                    }
                }

            default:
                Text("Unknown field type: \(field.type)")
                    .foregroundColor(.red)
            }
        }
    }
    
    private func clearChildFields(_ fields: [FormField]) {
        for field in fields {
            formData.removeValue(forKey: field.id)
            if let childFields = field.childFields {
                clearChildFields(childFields)
            }
        }
    }
}
